import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import './quotation.css';

import BASE from '../api';
import InlineSearch from './InlineSearch';
import { readJson, writeJson } from '../utils/storage';
import { resolveAssetUrl } from '../utils/url';

const QUOTE_DRAFT_KEY = 'quotation-ai/quote-draft';
const QUOTE_HISTORY_CACHE_KEY = 'quotation-ai/quote-history-cache';
const DEFAULT_ROOM_OPTIONS = [
  'Master Bath',
  'Common Bath',
  'Guest Bath',
  'Powder Room',
  'Kitchen',
  'Utility',
  'Balcony',
  'Living Room',
];

const blankClient = {
  client_name: '',
  mobile: '',
  email: '',
  company: '',
  gst: '',
  address: '',
};

const createBlankItem = () => ({
  name: '',
  room: '',
  price: '',
  quantity: 1,
  discount: 0,
  image: null,
  rawText: '',
  sku: '',
  size: '',
});

const PLACEHOLDER_IMAGE = '/static/images/Kohler/Image_Not_Found.png';
const BRAND_FALLBACK_IMAGES = {
  Kohler: '/kohler_cover.jpg',
  Aquant: '/hero.png',
};
const FORCE_IMAGE_BY_CODE = new Map([
  ['K-24740IN-7', PLACEHOLDER_IMAGE],
  ['K-704613IN-CP', '/static/images/Kohler/K-704613IN-CP.png'],
]);

const isPlaceholderImage = (value) =>
  String(value || '').includes('Image_Not_Found') || String(value || '').includes('Image not Found');

const isPageExtractedImage = (value) => {
  const val = String(value || '').toLowerCase();
  return (val.includes('_p') && val.includes('_i')) || val.includes('page');
};

const stripProductCode = (text = '') => {
  let val = String(text || '').trim();
  if (!val) return '';

  // 1. Remove leading code followed by ' - '
  const dashIndex = val.indexOf(' - ');
  if (dashIndex > 0) {
    const firstPart = val.substring(0, dashIndex).trim();
    const hasDigits = /\d/.test(firstPart);
    if (hasDigits && firstPart.length < 25) {
      val = val.substring(dashIndex + 3).trim();
    }
  }

  // 2. Remove trailing code in parentheses
  val = val.replace(/\s*[\(\[]\s*K-[A-Z0-9\-]+\s*[\)\]]/gi, '').trim();
  val = val.replace(/\s*[\(\[]\s*\d{4,}[A-Z0-9\-]*\s*[\)\]]/gi, '').trim();

  return val;
};


const extractLeadingCode = (value = '') => {
  const text = String(value || '').trim().toUpperCase();
  const match = text.match(/([A-Z0-9]+(?:-[A-Z0-9]+)+)/);
  return match ? match[1] : text;
};

const getItemCode = (item = {}) =>
  extractLeadingCode(item?.sku || item?.name || item?.text || item?.raw_item?.search_code || '');

const normalizeItemImage = (item = {}) => {
  const code = getItemCode(item);
  const forcedImage = FORCE_IMAGE_BY_CODE.get(code);
  if (forcedImage) {
    return forcedImage;
  }

  const primary = item.image || '';
  const secondary = item.raw_item?.images?.[0] || item.image || '';

  if (primary && !isPlaceholderImage(primary) && !isPageExtractedImage(primary)) {
    return primary;
  }
  if (secondary && !isPlaceholderImage(secondary) && !isPageExtractedImage(secondary)) {
    return secondary;
  }
  return null;
};

const formatDisplayDescription = (rawText = '', sku = '') => {
  if (!rawText) return '';

  const cleanSku = String(sku || '').trim();
  const norm = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
  const normSku = norm(cleanSku);

  const lines = String(rawText).split('\n');
  const cleanLines = [];

  for (let line of lines) {
    let trimmed = line.trim();
    if (!trimmed) continue;

    // Skip line if it is exactly the SKU
    if (norm(trimmed) === normSku) continue;

    // Remove price/MRP patterns
    trimmed = trimmed.replace(/mrp\s*(?:rs\.?|rs|INR|₹)?\s*[\d,\.\s`\/\-]*/gi, '');
    trimmed = trimmed.replace(/(?:rs\.?|rs|INR|₹)\s*[\d,\.\s`\/\-]*/gi, '');
    trimmed = trimmed.replace(/price\s*[\d,\.\s`\/\-]*/gi, '');

    // Remove the product's SKU if present in the text
    if (cleanSku) {
      const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const skuRegex = new RegExp(escapeRegExp(cleanSku), 'gi');
      trimmed = trimmed.replace(skuRegex, '');
    }
    // Safely remove only K- product codes and resulting empty brackets
    trimmed = trimmed.replace(/\bK-\d+[A-Z0-9\-]*\b/gi, '');
    trimmed = trimmed.replace(/\(\s*\)/g, '');
    trimmed = trimmed.replace(/\[\s*\]/g, '');
    // Clean up remaining punctuation and multiple spaces
    trimmed = trimmed.replace(/[\s\-\,\.\(\[\)\]\+\/]+$/, ''); // clean trailing punctuation
    trimmed = trimmed.replace(/^[\s\-\,\.\(\[\)\]\+\/]+/, ''); // clean leading punctuation
    trimmed = trimmed.replace(/\s+/g, ' ').trim();

    // Skip if line became empty or too short (e.g. just a few characters/leftover punctuation)
    if (trimmed.length < 3) continue;

    // Avoid duplicate lines in description
    if (!cleanLines.includes(trimmed)) {
      cleanLines.push(trimmed);
    }
  }

  return cleanLines.join('\n');
};

const sanitizeItem = (item = {}) => {
  const image = normalizeItemImage(item);
  const sku = String(item.sku || '').trim();
  let name = String(item.name || '').trim();

  // Name stripping logic removed because user explicitly wants the SKU code to be visible in the name string

  const rawText = formatDisplayDescription(item.rawText || '', sku);

  return {
    ...item,
    name,
    rawText,
    image,
    raw_item: item.raw_item
      ? {
          ...item.raw_item,
          images: image ? [image] : [],
        }
      : item.raw_item,
  };
};

const mapCartToItems = (cart = []) =>
  cart && cart.length > 0
    ? cart.map((item) => {
        const nameOnly = stripProductCode(item.name || '');
        const fullText = item.rawText || item.text || '';
        const lines = fullText.split('\n');
        if (lines.length > 0) {
          lines[0] = stripProductCode(lines[0]);
        }
        const cleanedFullText = lines.join('\n');

        return sanitizeItem({
          name: nameOnly,
          price: item.price || '0',
          quantity: 1,
          discount: 0,
          image: normalizeItemImage(item),
          room: '',
          rawText: cleanedFullText,
          sku: item.sku || '',
          size: item.size || '',
          raw_item: item.raw_item || item,
        });
      })
    : [createBlankItem()];

const normalizeQuoteHistory = (value) => (Array.isArray(value) ? value : []);

async function notifyQuoteReady(quoteNumber, grandTotal) {
  if (typeof window === 'undefined' || !('Notification' in window) || Notification.permission !== 'granted') {
    return;
  }

  const numericTotal = Number(grandTotal || 0);
  const title = quoteNumber ? `Quotation ${quoteNumber} ready` : 'Quotation ready';
  const body = Number.isFinite(numericTotal) && numericTotal > 0
    ? `PDF generated successfully. Grand total: Rs ${numericTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
    : 'Your quotation PDF is ready to view and share.';

  if ('serviceWorker' in navigator) {
    const registration = await navigator.serviceWorker.getRegistration();
    if (registration) {
      registration.showNotification(title, {
        body,
        icon: '/logo192.png',
        badge: '/logo192.png',
      });
      return;
    }
  }

  new Notification(title, { body, icon: '/logo192.png' });
}

function RoomCombobox({ value, options, placeholder, onValueChange }) {
  const [isOpen, setIsOpen] = useState(false);
  const [menuPlacement, setMenuPlacement] = useState('down');
  const [menuStyle, setMenuStyle] = useState(null);
  const [isSearching, setIsSearching] = useState(false);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      const clickedInsideField = wrapperRef.current && wrapperRef.current.contains(event.target);
      const clickedInsideMenu = menuRef.current && menuRef.current.contains(event.target);

      if (!clickedInsideField && !clickedInsideMenu) {
        setIsOpen(false);
        setIsSearching(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentValue = value || '';
  const normalizedValue = currentValue.trim().toLowerCase();
  
  // Show all options if not explicitly searching (i.e., on focus or click)
  const filteredOptions = isSearching 
    ? options.filter((option) => option.toLowerCase().includes(normalizedValue))
    : options;

  const hasExactMatch = options.some((option) => option.toLowerCase() === normalizedValue);
  const canUseTypedValue = currentValue.trim() && !hasExactMatch;

  const commitValue = (nextValue) => {
    onValueChange(nextValue);
    setIsOpen(false);
    setIsSearching(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  useEffect(() => {
    if (!isOpen || !wrapperRef.current) {
      return;
    }

    const updateMenuPosition = () => {
      if (!wrapperRef.current) {
        return;
      }

      const wrapperRect = wrapperRef.current.getBoundingClientRect();
      const menuHeight = Math.min(menuRef.current?.scrollHeight || 220, 220);
      const spaceBelow = window.innerHeight - wrapperRect.bottom;
      const spaceAbove = wrapperRect.top;
      const nextPlacement = spaceBelow < menuHeight + 24 && spaceAbove > spaceBelow ? 'up' : 'down';
      const viewportPadding = 16;
      const nextWidth = Math.min(
        Math.max(wrapperRect.width, 220),
        window.innerWidth - viewportPadding * 2
      );
      const nextLeft = Math.min(
        Math.max(wrapperRect.left, viewportPadding),
        window.innerWidth - viewportPadding - nextWidth
      );
      const nextTop = nextPlacement === 'up'
        ? Math.max(viewportPadding, wrapperRect.top - menuHeight - 8)
        : Math.min(window.innerHeight - viewportPadding - menuHeight, wrapperRect.bottom + 8);

      setMenuPlacement(nextPlacement);
      setMenuStyle({
        position: 'fixed',
        top: `${nextTop}px`,
        left: `${nextLeft}px`,
        width: `${nextWidth}px`,
      });
    };

    updateMenuPosition();
    window.addEventListener('resize', updateMenuPosition);
    window.addEventListener('scroll', updateMenuPosition, true);

    return () => {
      window.removeEventListener('resize', updateMenuPosition);
      window.removeEventListener('scroll', updateMenuPosition, true);
    };
  }, [isOpen, currentValue, options]);

  const menuContent = isOpen && (filteredOptions.length > 0 || canUseTypedValue) ? (
    <div
      ref={menuRef}
      className={`qt-room-combobox-menu ${menuPlacement === 'up' ? 'open-up' : ''}`}
      style={menuStyle || undefined}
    >
      {canUseTypedValue && (
        <button
          type="button"
          className="qt-room-combobox-option qt-room-combobox-option-create"
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => commitValue(currentValue.trim())}
        >
          Use "{currentValue.trim()}"
        </button>
      )}

      {filteredOptions.map((option) => (
        <button
          key={option}
          type="button"
          className={`qt-room-combobox-option ${option === currentValue ? 'active' : ''}`}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => commitValue(option)}
        >
          {option}
        </button>
      ))}
    </div>
  ) : null;

  return (
    <div
      ref={wrapperRef}
      className={`qt-room-combobox ${isOpen ? 'open' : ''} ${menuPlacement === 'up' ? 'open-up' : ''}`}
    >
      <input
        ref={inputRef}
        className="qt-field qt-room-field"
        name="room"
        value={currentValue}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(e) => {
          onValueChange(e.target.value);
          setIsOpen(true);
          setIsSearching(true);
        }}
        onFocus={() => {
          setIsOpen(true);
          setIsSearching(false);
        }}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setIsOpen(true);
          }
          if (e.key === 'Escape') {
            setIsOpen(false);
          }
        }}
      />
      <button
        type="button"
        className="qt-room-combobox-toggle"
        aria-label="Show room suggestions"
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => {
          setIsOpen((previous) => !previous);
          inputRef.current?.focus();
        }}
      >
        <span className="qt-room-combobox-caret" />
      </button>

      {typeof document !== 'undefined' && menuContent ? createPortal(menuContent, document.body) : null}
    </div>
  );
}


export default function Quotation({ cart }) {
  const [activeRoom, setActiveRoom] = useState('');
  // We no longer restore the draft on mount to ensure the page feels fresh on reload
  const [client, setClient] = useState(blankClient);
  const [showGstInput, setShowGstInput] = useState(false);
  const [items, setItems] = useState(() => mapCartToItems(cart));
  const [discountType, setDiscountType] = useState('percent'); // 'percent' or 'flat'
  const [discountValue, setDiscountValue] = useState(0);
  const [gstRate, setGstRate] = useState(18);
  const [quoteHistory, setQuoteHistory] = useState(() => normalizeQuoteHistory(readJson(QUOTE_HISTORY_CACHE_KEY, [])));
  const [generatedPdfUrl, setGeneratedPdfUrl] = useState(null);
  const [generatedPdfServerUrl, setGeneratedPdfServerUrl] = useState('');
  const [generatedPdfServerName, setGeneratedPdfServerName] = useState('');
  const [quoteNumber, setQuoteNumber] = useState('');
  const [quoteDate, setQuoteDate] = useState('');
  const [showBgLogo, setShowBgLogo] = useState(false);
  const [madeBy, setMadeBy] = useState('');
  const [madeByPhone, setMadeByPhone] = useState('');
  const [madeByEmail, setMadeByEmail] = useState('');
  const [isOffline, setIsOffline] = useState(() => (typeof navigator === 'undefined' ? false : !navigator.onLine));
  const [notificationPermission, setNotificationPermission] = useState(() =>
    typeof window !== 'undefined' && 'Notification' in window ? Notification.permission : 'default'
  );
  const [historySearchTerm, setHistorySearchTerm] = useState('');

  const customRoomOptions = Array.from(
    new Set(
      items
        .map((item) => (item.room || '').trim())
        .filter(Boolean)
    )
  )
    .filter(
      (roomName) =>
        !DEFAULT_ROOM_OPTIONS.some(
          (defaultOption) => defaultOption.toLowerCase() === roomName.toLowerCase()
        )
    )
    .sort((a, b) => a.localeCompare(b));

  const roomOptions = [...DEFAULT_ROOM_OPTIONS, ...customRoomOptions];

  const staffOptions = [
    { name: 'Harsh Bhai', phone: '+91 82385 21277' },
    { name: 'Karan Bhai', phone: '+91 82009 17069' },
    { name: 'Kunal Bhai', phone: '+91 98987 13167' },
  ];

  const handleStaffSelect = (e) => {
    const val = e.target.value;
    if (!val) {
      setMadeBy('');
      setMadeByPhone('');
      return;
    }
    const staff = staffOptions.find(s => s.name === val);
    if (staff) {
      setMadeBy(staff.name);
      setMadeByPhone(staff.phone);
    }
  };

  // Keyboard shortcut for Catalog Sync removed per user request to allow standard browser hard refresh

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${BASE}/list-quotes`);
      const normalized = res.data.quotes || [];
      setQuoteHistory(normalized);
      writeJson(QUOTE_HISTORY_CACHE_KEY, normalized);
    } catch (err) {
      console.error('Failed to fetch history', err);
      setQuoteHistory(normalizeQuoteHistory(readJson(QUOTE_HISTORY_CACHE_KEY, [])));
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  useEffect(() => {
    writeJson(QUOTE_DRAFT_KEY, {
      client,
      showGstInput,
      items,
      discountType,
      discountValue,
      gstRate,
      generatedPdfServerUrl,
      generatedPdfServerName,
      quoteNumber,
      quoteDate,
      showBgLogo,
      madeBy,
      madeByPhone,
      madeByEmail,
    });
  }, [
    client,
    showGstInput,
    items,
    discountType,
    discountValue,
    gstRate,
    generatedPdfServerUrl,
    generatedPdfServerName,
    quoteNumber,
    quoteDate,
    showBgLogo,
    madeBy,
    madeByPhone,
    madeByEmail,
  ]);

  useEffect(() => {
    const handleOnline = () => setIsOffline(false);
    const handleOffline = () => setIsOffline(true);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (cart.length === 0) {
      return;
    }

    setItems((previousItems) => {
      const isBlankDraft =
        previousItems.length === 1 &&
        !previousItems[0].name &&
        !previousItems[0].price &&
        !previousItems[0].rawText;

      return isBlankDraft ? mapCartToItems(cart) : previousItems.map(sanitizeItem);
    });
  }, [cart]);

  const requestNotificationPermission = async () => {
    if (typeof window === 'undefined' || !('Notification' in window)) {
      alert('Notifications are not supported on this device/browser.');
      return;
    }

    const permission = await Notification.requestPermission();
    setNotificationPermission(permission);

    if (permission === 'granted') {
      alert('Notifications enabled. You will get an alert when the quotation PDF is generated.');
    }
  };

  const loadQuote = async (id) => {
    try {
      const res = await axios.get(`${BASE}/get-quote/${id}`);
      const data = res.data;
      setClient({
        client_name: data.client_name || '',
        mobile: data.mobile || '',
        email: data.email || '',
        company: data.company || '',
        gst: data.gst || '',
        address: data.address || '',
      });
      setItems(data.items && data.items.length > 0 ? data.items.map(sanitizeItem) : [createBlankItem()]);
      setDiscountType(data.discount_type || 'percent');
      setDiscountValue(data.discount_type === 'flat' ? (data.discount_flat || 0) : (data.discount_percent || 0));
      setGstRate(data.gst_rate || 18);
      setShowGstInput(Boolean(data.gst));
      setGeneratedPdfUrl(null);
      setGeneratedPdfServerUrl('');
      setGeneratedPdfServerName('');
      setQuoteNumber(data.quote_number || '');
      setQuoteDate('');
      setShowBgLogo(Boolean(data.show_bg_logo));
      setMadeBy(data.made_by || '');
      setMadeByPhone(data.made_by_phone || '');
      setMadeByEmail(data.made_by_email || '');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      alert('Failed to load quotation');
    }
  };

  const deleteQuote = async (id) => {
    if (!window.confirm('Delete this quotation record?')) return;
    try {
      await axios.delete(`${BASE}/delete-quote/${id}`);
      fetchHistory();
    } catch (err) {
      alert('Delete failed');
    }
  };

  const handleClientChange = (e) => {
    setClient({ ...client, [e.target.name]: e.target.value });
  };

  const handleItemValueChange = (index, fieldName, fieldValue) => {
    setItems((previousItems) =>
      previousItems.map((item, itemIndex) =>
        itemIndex === index
          ? sanitizeItem({ ...item, [fieldName]: fieldValue })
          : sanitizeItem(item)
      )
    );
  };

  const handleItemChange = (index, e) => {
    handleItemValueChange(index, e.target.name, e.target.value);
  };

  const addItem = () => {
    setItems([...items.map(sanitizeItem), { ...createBlankItem(), room: activeRoom }]);
  };

  const removeItem = (index) => {
    const newItems = items.filter((_, i) => i !== index);
    setItems(
      newItems.length > 0
        ? newItems
        : [createBlankItem()]
    );
  };

  const startFreshDraft = () => {
    if (!window.confirm('Start a fresh quotation draft?')) {
      return;
    }

    setClient(blankClient);
    setShowGstInput(false);
    setItems(mapCartToItems(cart));
    setDiscountType('percent');
    setDiscountValue(0);
    setGstRate(18);
    setGeneratedPdfUrl(null);
    setGeneratedPdfServerUrl('');
    setGeneratedPdfServerName('');
    setQuoteNumber('');
    setQuoteDate('');
    setShowBgLogo(false);
    setMadeBy('');
    setMadeByPhone('');
    setMadeByEmail('');
  };

  const subtotal = items.reduce((sum, item) => {
    const qty = parseInt(item.quantity, 10) || 1;
    const price = parseFloat(item.price) || 0;
    const disc = parseFloat(item.discount) || 0;
    const total = price * qty;
    return sum + (total - (total * disc) / 100);
  }, 0);

  const discountAmount = discountType === 'flat' 
    ? parseFloat(discountValue || 0) 
    : subtotal * (parseFloat(discountValue || 0) / 100);

  const discountPercent = subtotal > 0 
    ? (discountAmount / subtotal) * 100 
    : 0;

  const taxableAmount = Math.max(0, subtotal - discountAmount);
  const gstAmount = taxableAmount * (parseFloat(gstRate || 0) / 100);
  const grandTotal = taxableAmount + gstAmount;
  const quoteFilename = `Quotation_${(client.client_name || 'Client').replace(/\s+/g, '_')}.pdf`;

  const formatMoney = (value) => {
    const num = Number(value || 0);
    return `Rs ${num.toFixed(2)}`;
  };

  const getItemTotal = (item) => {
    const qty = parseFloat(item.quantity) || 1;
    const price = parseFloat(item.price) || 0;
    const disc = parseFloat(item.discount) || 0;
    const gross = qty * price;
    return gross - (gross * disc) / 100;
  };

  // Group items by their Room/Section field
  const roomGroups = items.reduce((acc, item) => {
    let room = (item.room || '').trim().toUpperCase();
    if (!room) room = "GENERAL"; // Give it a default name if left empty

    if (!acc[room]) acc[room] = 0;

    const gross = getItemTotal(item); // gross after line-item discount

    // Apply global discount
    const globalDiscAmount = gross * (parseFloat(discountPercent || 0) / 100);
    const taxable = gross - globalDiscAmount;

    // Apply GST per-item to get true distributed Grand Total per room
    const itemGstAmount = taxable * (parseFloat(gstRate || 0) / 100);

    acc[room] += (taxable + itemGstAmount);

    return acc;
  }, {});

  // Convert grouped Object to Array with Index for rendering (e.g., 1. KID'S BATHROOM)
  const roomSummaries = Object.keys(roomGroups).map((roomName, idx) => ({
    index: idx + 1,
    name: roomName,
    total: roomGroups[roomName]
  }));

  const buildDetailedShareText = () => {
    const lines = [];
    lines.push(`Quotation for ${client.client_name || 'Customer'}`);
    if (client.company) lines.push(`Company: ${client.company}`);
    if (client.mobile) lines.push(`Mobile: ${client.mobile}`);
    if (client.email) lines.push(`Email: ${client.email}`);
    if (client.address) lines.push(`Address: ${client.address}`);
    if (client.gst) lines.push(`GSTIN: ${client.gst}`);
    lines.push('');
    lines.push('Items:');
    items.forEach((item, index) => {
      const name = item.name || `Item ${index + 1}`;
      const qty = parseFloat(item.quantity) || 1;
      const price = parseFloat(item.price) || 0;
      const disc = parseFloat(item.discount) || 0;
      const lineTotal = getItemTotal(item);
      lines.push(
        `${index + 1}. ${name} | Qty: ${qty} | Price: ${formatMoney(price)} | Disc: ${disc}% | Total: ${formatMoney(lineTotal)}`
      );
    });
    lines.push('');
    lines.push(`Final Amount: ${formatMoney(subtotal)}`);
    if (discountAmount > 0) {
      lines.push(`Discount: ${parseFloat(discountPercent || 0).toFixed(2)}% (${formatMoney(discountAmount)})`);
    }
    lines.push(`Taxable Amount: ${formatMoney(taxableAmount)}`);
    if (gstRate > 0) {
      lines.push(`GST (${parseFloat(gstRate || 0)}%): ${formatMoney(gstAmount)}`);
    }
    lines.push(`Grand Total: ${formatMoney(grandTotal)}`);
    return lines.join('\n');

  };

  const getPdfFile = async () => {
    const response = await fetch(generatedPdfUrl);
    const blob = await response.blob();
    return new File([blob], generatedPdfServerName || quoteFilename, { type: 'application/pdf' });
  };

  const downloadGeneratedPdf = () => {
    const link = document.createElement('a');
    link.href = generatedPdfUrl;
    link.download = generatedPdfServerName || quoteFilename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getWhatsappNumber = () => {
    const mobileRaw = String(client.mobile || '').trim();
    const mobileDigits = mobileRaw.replace(/\D/g, '');
    if (mobileDigits.length === 10) return `91${mobileDigits}`;
    if (mobileDigits.length === 11 && mobileDigits.startsWith('0')) return `91${mobileDigits.slice(1)}`;
    if (mobileDigits.length >= 12 && mobileDigits.startsWith('91')) return mobileDigits;
    return '';
  };

  const generatePDF = async () => {
    if (isOffline) {
      alert('You are offline. Please reconnect to generate a fresh PDF from the backend.');
      return;
    }

    try {
      const payload = {
        ...client,
        items,
        discount_type: discountType,
        discount_flat: discountType === 'flat' ? parseFloat(discountValue || 0) : 0,
        discount_percent: parseFloat(discountPercent || 0),
        gst_rate: parseFloat(gstRate || 0),
        subtotal,
        discount_amount: discountAmount,
        taxable_amount: taxableAmount,
        gst_amount: gstAmount,
        grand_total: grandTotal,
        show_bg_logo: showBgLogo,
        made_by: madeBy.trim(),
        made_by_phone: madeByPhone.trim(),
        made_by_email: madeByEmail.trim(),
      };

      const response = await axios.post(`${BASE}/generate-quote`, payload, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
      setGeneratedPdfUrl(url);
      const serverPath = response.headers['x-quote-file-url'] || '';
      const serverName = response.headers['x-quote-file-name'] || '';
      const qNum = response.headers['x-quote-number'] || '';
      const serverUrl = serverPath ? resolveAssetUrl(serverPath) : '';
      setGeneratedPdfServerUrl(serverUrl);
      setGeneratedPdfServerName(serverName || '');
      setQuoteNumber(qNum);
      const today = new Date();
      const formattedDate = today.toLocaleDateString('en-IN', { day: '2-digit', month: 'long', year: 'numeric' });
      setQuoteDate(formattedDate);
      fetchHistory();
      await notifyQuoteReady(qNum, grandTotal);
    } catch (error) {
      console.error('Error generating PDF', error);
      alert('Failed to generate PDF');
    }
  };

  const handleSystemShare = async () => {
    if (!generatedPdfUrl) return;

    try {
      const file = await getPdfFile();
      const shareMessage = buildDetailedShareText();

      const shareData = {
        title: `Quotation from ${client.company || 'Our Company'}`,
        text: shareMessage,
        files: [file],
      };

      if (navigator.canShare && navigator.canShare({ files: [file] })) {
        await navigator.share(shareData);
      } else {
        downloadGeneratedPdf();
        alert('System file share not supported on this browser. PDF downloaded, please share manually.');
      }
    } catch (error) {
      console.error('Error sharing file:', error);
    }
  };

  const handleWhatsAppShare = async () => {
    if (!generatedPdfUrl) return;
    try {
      const whatsappNumber = getWhatsappNumber();

      const itemLines = items.map((item, i) => {
        const qty = parseFloat(item.quantity) || 1;
        const price = parseFloat(item.price) || 0;
        const disc = parseFloat(item.discount) || 0;
        const total = getItemTotal(item);
        return `  ${i + 1}. ${item.name || `Item ${i + 1}`} (${qty}x) → ₹${price.toLocaleString('en-IN')} | Disc: ${disc}% | Total: ₹${total.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
      }).join('\n');

      // FULL QUOTATION DETAILS
      const fullMsg = [
        showBgLogo ? `🏢 *SHREEJI CERAMICA*` : null,
        showBgLogo ? `Redefining Luxury | Ph: 9033745455` : null,
        showBgLogo ? `═══════════════════════════════════` : null,
        ``,
        `📋 *QUOTATION*`,
        `Quotation #: ${quoteNumber || 'N/A'}`,
        `Date: ${quoteDate || new Date().toLocaleDateString('en-IN')}`,
        ``,
        `👤 *CLIENT INFORMATION*`,
        `Name: ${client.client_name || 'N/A'}`,
        client.mobile ? `Mobile: ${client.mobile}` : null,
        client.company ? `Company: ${client.company}` : null,
        client.address ? `Address: ${client.address}` : null,
        client.gst ? `GSTIN: ${client.gst}` : null,
        ``,
        `📦 *ITEMS*`,
        itemLines,
        ``,
        `💰 *FINANCIAL BREAKDOWN*`,
        `Final Amount: ₹${subtotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,
        discountAmount > 0 ? `Discount (${discountPercent.toFixed(2)}%): -₹${discountAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : null,
        `Taxable Amount: ₹${taxableAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,
        gstRate > 0 ? `GST (${gstRate}%): +₹${gstAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : null,
        ``,
        `*🎯 GRAND TOTAL: ₹${grandTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}*`,

        ``,
        `📄 PDF: ${generatedPdfServerUrl}`,
        ``,
        `Thank you! 🙏`,
        `www.shreejiceramica.com`,
      ].filter(l => l !== null).join('\n');

      const waUrl = whatsappNumber
        ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(fullMsg)}`
        : `https://wa.me/?text=${encodeURIComponent(fullMsg)}`;

      window.open(waUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Error sharing on WhatsApp:', error);
      alert('Unable to open WhatsApp share.');
    }
  };

  const handleWhatsAppAPIShare = async () => {
    if (!generatedPdfUrl || !generatedPdfServerUrl) {
      alert('PDF not ready. Please generate PDF first.');
      return;
    }

    try {
      const whatsappNumber = getWhatsappNumber();

      // ONLY PDF MESSAGE
      const pdfMsg = [
        `📄 *PDF QUOTATION*`,
        ``,
        `Quotation: ${quoteNumber || 'N/A'}`,
        `Date: ${quoteDate || new Date().toLocaleDateString('en-IN')}`,
        `Client: ${client.client_name || 'Customer'}`,
        `Total: ₹${grandTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,
        ``,
        `📥 Download PDF:`,
        `${generatedPdfServerUrl}`,
      ].join('\n');

      const waUrl = whatsappNumber
        ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(pdfMsg)}`
        : `https://wa.me/?text=${encodeURIComponent(pdfMsg)}`;

      window.open(waUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Error sharing PDF on WhatsApp:', error);
      alert('Unable to open WhatsApp share.');
    }
  };

  const handleEmailShare = async () => {
    if (!generatedPdfUrl) return;
    try {
      const recipient = String(client.email || '').trim();
      if (!recipient) {
        alert('Please enter client email ID before sending email.');
        return;
      }

      const pdfLink = generatedPdfServerUrl || '';
      const subject = showBgLogo ? `Quotation ${quoteNumber} — Shreeji Ceramica` : `Quotation ${quoteNumber}`;
      const body = [
        `Dear ${client.client_name || 'Customer'},`,
        ``,
        showBgLogo ? `Thank you for your interest in Shreeji Ceramica — Redefining Luxury.` : `Thank you for your interest.`,
        ``,
        `Please find your quotation details below:`,
        ``,
        `Quotation No : ${quoteNumber || 'N/A'}`,
        `Date         : ${quoteDate || new Date().toLocaleDateString('en-IN')}`,
        client.company ? `Company      : ${client.company}` : null,
        client.address ? `Address      : ${client.address}` : null,
        client.gst ? `GSTIN        : ${client.gst}` : null,
        ``,
        `Items:`,
        ...items.map((item, i) => {
          const qty = parseFloat(item.quantity) || 1;
          const price = parseFloat(item.price) || 0;
          const disc = parseFloat(item.discount) || 0;
          const total = getItemTotal(item);
          return `${i + 1}. ${item.name || `Item ${i + 1}`} | Qty: ${qty} | Rs ${price.toLocaleString('en-IN')} | Disc: ${disc}% | Total: Rs ${total.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
        }),
        ``,
        `Final Amount  : Rs ${subtotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,
        discountAmount > 0 ? `Discount (${discountPercent.toFixed(2)}%) : -Rs ${discountAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : null,
        `Taxable Amount: Rs ${taxableAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,
        gstRate > 0 ? `GST (${gstRate}%)    : +Rs ${gstAmount.toLocaleString('en-IN', { maximumFractionDigits: 2 })}` : null,
        `Grand Total   : Rs ${grandTotal.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`,

        ``,
        pdfLink ? `Download PDF: ${pdfLink}` : null,
        ``,
        showBgLogo ? `For any queries, contact us at:` : null,
        showBgLogo ? `Phone : 9033745455` : null,
        showBgLogo ? `Email : shreejiceramica303@gmail.com` : null,
        showBgLogo ? `Web   : www.shreejiceramica.com` : null,
        ``,
        `Warm regards,`,
        showBgLogo ? `Shreeji Ceramica Team` : `Sales Team`,
      ].filter(l => l !== null).join('\n');

      // Try Gmail compose URL first (opens Gmail in browser directly)
      const gmailUrl = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(recipient)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
      window.open(gmailUrl, '_blank', 'noopener,noreferrer');
    } catch (error) {
      console.error('Error sharing on Email:', error);
      alert('Unable to open Gmail.');
    }
  };

  return (
    <div className="qt-root">
      <header className="qt-header">
        <div className="qt-header-row">
          <div>
            <h2>Create New Quotation</h2>
          </div>
          <div className="qt-header-actions">
            <button className="qt-reset-btn" onClick={startFreshDraft}>
              Start Fresh
            </button>
          </div>
        </div>
      </header>

      {(isOffline || generatedPdfServerUrl || notificationPermission === 'granted') && (
        <div className={`qt-status-banner ${isOffline ? 'offline' : 'info'}`}>
          {isOffline && <span>Offline mode active. Draft editing works, but fresh PDF generation needs internet.</span>}
          {!isOffline && generatedPdfServerUrl && <span>Latest PDF link saved. You can reopen and share it later.</span>}
          {notificationPermission === 'granted' && <span>Notifications enabled for PDF-ready alerts.</span>}
        </div>
      )}

      <section className="qt-client-grid" style={{ position: 'relative', zIndex: 9999 }}>
        <input
          className="qt-field"
          name="client_name"
          value={client.client_name}
          placeholder="Client Name"
          onChange={handleClientChange}
        />
        <input
          className="qt-field"
          name="mobile"
          value={client.mobile}
          placeholder="Mobile Number"
          onChange={handleClientChange}
        />
        <input
          className="qt-field"
          name="company"
          value={client.company}
          placeholder="Company Name"
          onChange={handleClientChange}
        />
        <input
          className="qt-field"
          type="email"
          name="email"
          value={client.email}
          placeholder="Email ID"
          onChange={handleClientChange}
        />

        <div className="qt-span-2">
          <input
            className="qt-field"
            name="address"
            value={client.address}
            placeholder="Address"
            onChange={handleClientChange}
          />
        </div>

        {showGstInput ? (
          <input
            className="qt-field"
            name="gst"
            value={client.gst}
            placeholder="Client GSTIN"
            autoFocus
            onChange={handleClientChange}
          />
        ) : (
          <button className="qt-gst-btn" onClick={() => setShowGstInput(true)}>
            + Add GSTIN Detail
          </button>
        )}

        <InlineSearch 
          onAdd={(newItem) => {
            if (!newItem) return;
            const itemWithRoom = { ...newItem, room: activeRoom };
            setItems((prev) => {
              // Replace the first item if it's completely blank
              const isFirstBlank = prev.length === 1 && !prev[0].name && !prev[0].price && !prev[0].rawText && !prev[0].sku;
              if (isFirstBlank) {
                return [itemWithRoom];
              }
              return [...prev, itemWithRoom];
            });
            
            // Visual feedback
            const toast = document.createElement('div');
            toast.textContent = `Added: ${newItem.name || 'Product'}`;
            toast.style.cssText = `
              position: fixed; bottom: 30px; right: 30px;
              background: #10b981; color: white; padding: 12px 24px;
              border-radius: 12px; font-weight: 600; z-index: 10002;
              box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05);
              transition: opacity 0.4s cubic-bezier(0.4, 0, 0.2, 1), transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
              transform: translateY(0);
            `;
            document.body.appendChild(toast);
            setTimeout(() => {
              toast.style.opacity = '0';
              toast.style.transform = 'translateY(20px)';
              setTimeout(() => {
                if (document.body.contains(toast)) document.body.removeChild(toast);
              }, 400);
            }, 2500);
          }} 
        />
      </section>

      <section className="qt-items-section" style={{ position: 'relative', zIndex: 1 }}>
        <div className="qt-items-head" style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0 }}>Itemized List</h3>
          
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
              CURRENT ROOM:
            </span>
            <RoomCombobox
              value={activeRoom}
              options={roomOptions}
              placeholder="Select or Create Section..."
              onValueChange={setActiveRoom}
            />
          </div>

          <button onClick={addItem} className="qt-add-row" style={{ marginLeft: 'auto' }}>
            + Add Row
          </button>
        </div>

        <div className="qt-items-list">
          {items.map((item, index) => (
            <article key={index} className="qt-item-card">
              <div className="qt-item-grid">
                <div 
                  className="qt-thumb" 
                  style={{ cursor: 'pointer' }}
                  onClick={() => {
                    const input = document.createElement('input');
                    input.type = 'file';
                    input.accept = 'image/*';
                    input.onchange = async (e) => {
                      const file = e.target.files[0];
                      if (!file) return;
                      const formData = new FormData();
                      formData.append("file", file);
                      try {
                        const res = await fetch(`${BASE}/upload-image`, { method: "POST", body: formData });
                        if (res.ok) {
                          const data = await res.json();
                          handleItemValueChange(index, 'image', data.url);
                        }
                      } catch (err) {
                        console.error("Upload failed", err);
                      }
                    };
                    input.click();
                  }}
                  title="Click to upload image"
                >
                  {normalizeItemImage(item) ? (
                    <img src={resolveAssetUrl(normalizeItemImage(item))} alt="thumb" />
                  ) : (
                    <div className="qt-no-thumb">No Image</div>
                  )}
                </div>

                <input
                  className="qt-field qt-name-field"
                  name="name"
                  value={item.name || ''}
                  placeholder="Item Name"
                  onChange={(e) => handleItemChange(index, e)}
                />
                <RoomCombobox
                  value={item.room || ''}
                  options={roomOptions}
                  placeholder="Room/Section"
                  onValueChange={(nextValue) => handleItemValueChange(index, 'room', nextValue)}
                />
                <input
                  className="qt-field"
                  name="price"
                  type="number"
                  value={item.price}
                  placeholder="Price"
                  onChange={(e) => handleItemChange(index, e)}
                />
                <input
                  className="qt-field"
                  name="quantity"
                  type="number"
                  value={item.quantity}
                  placeholder="Qty"
                  onChange={(e) => handleItemChange(index, e)}
                />
                <input
                  className="qt-field"
                  name="sku"
                  value={item.sku || ''}
                  placeholder="SKU"
                  onChange={(e) => {
                    const newSku = e.target.value;
                    handleItemValueChange(index, 'sku', newSku);
                    const currentName = (item.name || '').trim();
                    const oldSku = (item.sku || '').trim();
                    if (!currentName || currentName === oldSku) {
                      handleItemValueChange(index, 'name', newSku);
                    } else if (oldSku && currentName.startsWith(oldSku + ' - ')) {
                      const restOfName = currentName.substring(oldSku.length + 3);
                      handleItemValueChange(index, 'name', newSku ? `${newSku} - ${restOfName}` : restOfName);
                    }
                  }}
                />
                <input
                  className="qt-field"
                  name="size"
                  value={item.size || ''}
                  placeholder="Size"
                  onChange={(e) => handleItemChange(index, e)}
                />
                <input
                  className="qt-field"
                  name="discount"
                  type="number"
                  value={item.discount}
                  placeholder="Disc %"
                  onChange={(e) => handleItemChange(index, e)}
                />

                <button className="qt-remove-btn" onClick={() => removeItem(index)}>
                  x
                </button>
              </div>

              <div className="qt-detail-wrap">
              <textarea
                  className="qt-detail-area"
                  name="rawText"
                  value={item.rawText || ''}
                  placeholder="Complete item details (specifications, size, etc.)"
                  onChange={(e) => handleItemChange(index, e)}
                />
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* ── PDF Options ────────────────────────────────────────── */}
      {roomSummaries.length > 0 && (
        <div className="qt-room-summary-table-wrap">
          <table className="qt-room-summary-table">
            <thead>
              <tr>
                <th colSpan="2">SUMMARY OF ALL BATH ROOM</th>
              </tr>
            </thead>
            <tbody>
              {roomSummaries.map((smry, idx) => (
                <tr key={idx}>
                  <td>{smry.index}. {smry.name}</td>
                  <td>Rs {smry.total.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
                </tr>
              ))}
              <tr className="qt-room-summary-total">
                <td>FINAL AMOUNT</td>
                <td>Rs {roomSummaries.reduce((a, b) => a + b.total, 0).toLocaleString('en-IN', { maximumFractionDigits: 0 })}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <section className="qt-pdf-options">
        <h4>PDF Options</h4>
        <div className="qt-pdf-opts-row">
          <label className="qt-bg-logo-label">
            <input
              type="checkbox"
              id="bg-logo-checkbox"
              checked={showBgLogo}
              onChange={(e) => setShowBgLogo(e.target.checked)}
              className="qt-bg-logo-check"
            />
            <span className="qt-bg-logo-icon">🏢</span>
            Include Shreeji Office Branding (Letterhead)
          </label>
          <button
            type="button"
            className={`qt-notify-btn ${notificationPermission === 'granted' ? 'enabled' : ''}`}
            onClick={requestNotificationPermission}
          >
            {notificationPermission === 'granted' ? 'Notifications Enabled' : 'Enable Notifications'}
          </button>
        </div>

        <div className="qt-madeby-section">
          <p className="qt-madeby-title">👤 PREPARED BY <span>(Select or Type)</span></p>
          <div className="qt-madeby-fields">

            {/* ── Dropdown: select from staff list ── */}
            <div className="qt-madeby-wrap" style={{ gridColumn: 'span 2' }}>
              <select
                className="qt-field qt-madeby-input"
                id="staff-select"
                value={staffOptions.some(s => s.name === madeBy) ? madeBy : ''}
                onChange={handleStaffSelect}
              >
                <option value="">— Select Staff —</option>
                {staffOptions.map(staff => (
                  <option key={staff.name} value={staff.name}>
                    {staff.name} — {staff.phone}
                  </option>
                ))}
              </select>
            </div>

            {/* ── Manual input: type any name ── */}
            <div className="qt-madeby-wrap" style={{ gridColumn: 'span 2' }}>
              <input
                className="qt-field qt-madeby-input"
                type="text"
                placeholder="Or type name manually..."
                value={madeBy}
                onChange={(e) => {
                  setMadeBy(e.target.value);
                  // If manually typed, clear phone (not from staff list)
                  const matched = staffOptions.find(s => s.name === e.target.value);
                  setMadeByPhone(matched ? matched.phone : '');
                  setMadeByEmail(matched ? (matched.email || '') : '');
                }}
              />
            </div>

            {/* ── Phone: shown when staff selected or auto-filled ── */}
            {madeBy && madeByPhone && (
              <div className="qt-madeby-wrap">
                <input
                  className="qt-field qt-madeby-input"
                  type="text"
                  placeholder="Staff Phone"
                  value={madeByPhone}
                  onChange={(e) => setMadeByPhone(e.target.value)}
                />
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="qt-summary">
        <h4>Financial Summary</h4>

        <div className="qt-summary-row">
          <span>Final Amount</span>
          <strong>Rs {subtotal.toFixed(2)}</strong>
        </div>

        <div className="qt-summary-row">
          <span>Extra Discount</span>
          <div className="qt-discount-input-group">
            <div className="qt-discount-toggle-buttons">
              <button
                type="button"
                className={`qt-discount-toggle-btn ${discountType === 'percent' ? 'active' : ''}`}
                onClick={() => setDiscountType('percent')}
              >
                Percentage
              </button>
              <button
                type="button"
                className={`qt-discount-toggle-btn ${discountType === 'flat' ? 'active' : ''}`}
                onClick={() => setDiscountType('flat')}
              >
                MRP
              </button>
            </div>
            <input
              className="qt-mini-input"
              type="number"
              min="0"
              value={discountValue}
              onChange={(e) => setDiscountValue(e.target.value)}
            />
          </div>
        </div>


        <div className="qt-summary-row">
          <span>GST Rate (%)</span>
          <select className="qt-mini-select" value={gstRate} onChange={(e) => setGstRate(parseFloat(e.target.value))}>
            {[0, 5, 12, 18, 28].map((r) => (
              <option key={r} value={r}>
                {r === 0 ? "None" : `${r}%`}
              </option>
            ))}
          </select>
        </div>


        {gstRate > 0 && (
          <div className="qt-summary-row gst">
            <span>Estimated GST</span>
            <strong>+ Rs {gstAmount.toFixed(2)}</strong>
          </div>
        )}

        <div className="qt-total-row">
          <span>Grand Total</span>
          <strong>Rs {grandTotal.toFixed(2)}</strong>
        </div>

        {!generatedPdfUrl ? (
          <button onClick={generatePDF} className="qt-generate-btn">
            GENERATE PDF
          </button>
        ) : (
          <div className="qt-pdf-actions">
            {/* Quote number badge */}
            {quoteNumber && (
              <div className="qt-quote-info">
                <span className="qt-quote-num">🔖 {quoteNumber}</span>
                <span className="qt-quote-dt">📅 {quoteDate}</span>
              </div>
            )}

            <div className="qt-pdf-links">
              <a href={generatedPdfUrl} target="_blank" rel="noreferrer" className="qt-pdf-view">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                View PDF
              </a>
              <a href={generatedPdfUrl} download={generatedPdfServerName || quoteFilename} className="qt-pdf-download">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                Download PDF
              </a>
            </div>

            <div className="qt-share-row">
              <button onClick={handleWhatsAppAPIShare} className="qt-share-btn qt-wa-btn qt-wa-api-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" /></svg>
                PDF Only <span className="qt-pdf-badge">Link</span>
              </button>
              <button onClick={handleEmailShare} className="qt-share-btn qt-gmail-btn">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M24 5.457v13.909c0 .904-.732 1.636-1.636 1.636h-3.819V11.73L12 16.64l-6.545-4.91v9.273H1.636A1.636 1.636 0 010 19.366V5.457c0-2.023 2.309-3.178 3.927-1.964L5.455 4.64 12 9.548l6.545-4.910 1.528-1.145C21.69 2.28 24 3.434 24 5.457z" /></svg>
                Send Gmail
              </button>
            </div>

            <div className="qt-share-row-alt">
              <button onClick={handleWhatsAppShare} className="qt-share-btn qt-wa-btn-chat">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" /></svg>
                Full Details
              </button>
              <button onClick={handleSystemShare} className="qt-share-btn qt-system-btn">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" /></svg>
                Share More
              </button>
            </div>

            <button
              onClick={() => {
                setGeneratedPdfUrl(null);
                setGeneratedPdfServerUrl('');
                setGeneratedPdfServerName('');
                setQuoteNumber('');
                setQuoteDate('');
              }}
              className="qt-edit-btn"
            >
              ✏️ Edit Again
            </button>
          </div>
        )}
      </section>

      <section className="qt-history">
        <div className="qt-history-line" />
        <div className="qt-history-top">
          <h3 className="qt-history-title">
            Quotation History
            <span className="qt-count-pill">{quoteHistory.length} files</span>
          </h3>
          <div className="qt-history-search">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
            <input 
              type="text" 
              placeholder="Find client or quote..." 
              value={historySearchTerm}
              onChange={(e) => setHistorySearchTerm(e.target.value)}
            />
          </div>
        </div>

        {(() => {
          const filtered = quoteHistory.filter(q => 
            q.client.toLowerCase().includes(historySearchTerm.toLowerCase()) ||
            (q.id && q.id.toLowerCase().includes(historySearchTerm.toLowerCase()))
          );

          if (filtered.length === 0) {
            return (
              <div className="qt-history-empty">
                <p>{historySearchTerm ? "No matching records found." : "No quotation records found yet."}</p>
              </div>
            );
          }

          // Grouping logic
          const now = new Date();
          const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
          const yesterday = today - 86400000;

          const groups = { Today: [], Yesterday: [], Older: [] };
          filtered.forEach(q => {
             const ts = q.date * 1000;
             if (ts >= today) groups.Today.push(q);
             else if (ts >= yesterday) groups.Yesterday.push(q);
             else groups.Older.push(q);
          });

          return Object.entries(groups).map(([label, records]) => {
            if (records.length === 0) return null;
            return (
              <div key={label} className="qt-history-group">
                <h4 className="qt-group-label">{label}</h4>
                <div className="qt-records-list">
                  {records.map(q => {
                    const initials = (q.client || 'C').charAt(0).toUpperCase();
                    return (
                      <article key={q.id} className="qt-record-list-item">
                        <div className="qt-record-avatar" style={{ '--bg': `hsl(${(initials.charCodeAt(0) * 10) % 360}, 65%, 45%)` }}>
                          {initials}
                        </div>
                        <div className="qt-record-main">
                          <div className="qt-record-info">
                            <span className="qt-record-name">{q.client}</span>
                            <span className="qt-record-date">
                              📅 {new Date(q.date * 1000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })} • 
                              {new Date(q.date * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <div className="qt-record-amount">
                            ₹{q.total.toLocaleString('en-IN')}
                          </div>
                        </div>
                        <div className="qt-record-row-actions">
                          <button onClick={() => loadQuote(q.id)} className="qt-action-icon edit" title="Resume Edit">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>
                          </button>
                          <button onClick={() => deleteQuote(q.id)} className="qt-action-icon delete" title="Delete">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
                          </button>
                        </div>
                      </article>
                    );
                  })}
                </div>
              </div>
            );
          });
        })()}
      </section>
    </div>
  );
}
