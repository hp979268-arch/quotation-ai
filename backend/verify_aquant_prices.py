import json

with open('c:/Movies/quotation-ai/quotation-ai/backend/search_index_v2.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

aquant_items = [i for i in d.get('stored_items',[]) if i.get('brand') == 'Aquant']
print(f'Total Aquant: {len(aquant_items)}')

# Check zero/empty price
zero_price = [i for i in aquant_items if not i.get('price') or str(i.get('price','')).strip() in ['0','0.0','','None']]
print(f'Zero/empty price: {len(zero_price)}')

# Print 10 samples showing code, price, variant_prices
print('\n--- Sample of Aquant prices ---')
for item in aquant_items[:20]:
    code = item['search_code']
    price = item.get('price','N/A')
    vp = item.get('variant_prices', {})
    print(f'{code} -> price={price} | variant_prices={vp}')

# Check items where price seems wrong
print('\n--- Items with 0 price ---')
for item in zero_price[:10]:
    print(item['search_code'], '|', item.get('price'), '|', item.get('name','')[:60])
