const fs = require('fs');
const { MongoClient } = require('mongodb');
require('dotenv').config({ path: 'backend/.env' });

const uri = process.env.MONGO_URI;

async function run() {
  if (!uri) {
    console.error("MONGO_URI not found");
    return;
  }
  
  const client = new MongoClient(uri);
  
  try {
    await client.connect();
    const db = client.db('quotation_ai'); // try this DB
    let collections = await db.listCollections().toArray();
    let colName = 'stored_items';
    
    if (collections.length === 0) {
      const db2 = client.db('test');
      collections = await db2.listCollections().toArray();
      colName = collections.some(c => c.name === 'stored_items') ? 'stored_items' : 'search_index';
      if (!collections.some(c => c.name === colName)) {
        colName = 'products';
      }
      var col = db2.collection(colName);
    } else {
      colName = collections.some(c => c.name === 'stored_items') ? 'stored_items' : 'search_index';
      var col = db.collection(colName);
    }

    const liveDocs = await col.find({}).toArray();
    console.log(`Loaded ${liveDocs.length} records from live DB.`);
    
    const localData = JSON.parse(fs.readFileSync('backend/search_index_v2.json', 'utf8'));
    const localItems = localData.stored_items || [];
    
    const localMap = {};
    for (const item of localItems) {
      if (item.search_code) {
        localMap[item.search_code] = item;
      }
    }
    
    const mismatches = [];
    
    for (const doc of liveDocs) {
      const sc = doc.search_code;
      if (!sc) continue;
      
      const local = localMap[sc];
      if (!local) {
        mismatches.push(`Missing locally: ${sc}`);
        continue;
      }
      
      const lp = String(local.price || '');
      const dp = String(doc.price || '');
      if (lp !== dp) {
        mismatches.push(`PRICE MISMATCH: ${sc} -> Live: ${dp}, Local: ${lp}`);
      }
      
      const limg = (local.images && local.images[0]) ? local.images[0].split('?')[0] : '';
      const dimg = (doc.images && doc.images[0]) ? doc.images[0].split('?')[0] : '';
      
      if (limg !== dimg) {
        mismatches.push(`IMAGE MISMATCH: ${sc} -> Live: ${dimg}, Local: ${limg}`);
      }
      
      // Check colors if present
      const lcolor = local.color || '';
      const dcolor = doc.color || '';
      if (lcolor !== dcolor) {
        mismatches.push(`COLOR MISMATCH: ${sc} -> Live: ${dcolor}, Local: ${lcolor}`);
      }
    }
    
    console.log(`\nFound ${mismatches.length} mismatches.`);
    for (let i = 0; i < Math.min(20, mismatches.length); i++) {
      console.log(mismatches[i]);
    }
    
    if (mismatches.length === 0) {
      console.log("100% Match! The live website is perfectly synced with the local data.");
    }
    
  } finally {
    await client.close();
  }
}

run().catch(console.dir);
