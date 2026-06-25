import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import './search.css';

import BASE from '../api';
import { resolveAssetUrl } from '../utils/url';
import { sanitizeDisplayText } from '../utils/text';

const MIN_QUERY_LENGTH = 2;
const MAX_MENU_HEIGHT = 380;
const VIEWPORT_PADDING = 12;
const FORCE_PDF_IMAGE_CODES = new Set([]);
const BRAND_FALLBACK_IMAGES = {
  Kohler: '/kohler_cover.jpg',
  Aquant: '/hero.png',
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


function ImageNotFoundBox() {
  return (
    <div
      title="Image Not Found"
      style={{
        width: '64px',
        height: '64px',
        borderRadius: '10px',
        border: '1px dashed rgba(248, 113, 113, 0.45)',
        background: 'rgba(248, 113, 113, 0.07)',
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '2px',
      }}
    >
      <span style={{ fontSize: '16px', lineHeight: 1 }}>🚫</span>
      <span
        style={{
          fontSize: '7px',
          fontWeight: 800,
          color: 'rgba(248, 113, 113, 0.9)',
          textAlign: 'center',
          lineHeight: 1.2,
          letterSpacing: '0.02em',
          textTransform: 'uppercase',
        }}
      >
        No Image
      </span>
    </div>
  );
}

function SuggestionThumbnail({ suggestion, product }) {
  const [failedPrimary, setFailedPrimary] = useState(false);

  const candidateImage = resolveSuggestionImage(product || {}, suggestion || {});
  const isPlaceholder =
    String(candidateImage || '').toLowerCase().includes('image_not_found') ||
    String(candidateImage || '').toLowerCase().includes('image not found');

  // No image URL at all, or it is a known placeholder → show "No Image" box immediately
  if (!candidateImage || isPlaceholder) {
    return <ImageNotFoundBox />;
  }

  const primarySrc = resolveAssetUrl(candidateImage);

  // Image URL exists but failed to load → show "No Image" box
  if (failedPrimary) {
    return <ImageNotFoundBox />;
  }

  return (
    <img
      src={primarySrc}
      alt=""
      onError={() => setFailedPrimary(true)}
      style={{
        width: '64px',
        height: '64px',
        objectFit: 'contain',
        background: '#ffffff',
        borderRadius: '10px',
        padding: '10px',
        border: '1px solid rgba(95, 99, 104, 0.15)',
        flexShrink: 0,
      }}
    />
  );
}

function getProductCode(product = {}, suggestion = {}) {
  return String(
    product.search_code
    || product.base_code
    || product.name
    || suggestion.text
    || suggestion.full_name
    || suggestion.display_code
    || ''
  ).trim().toUpperCase();
}

function resolveSuggestionImage(product = {}, suggestion = {}) {
  const code = getProductCode(product, suggestion);
  if (FORCE_PDF_IMAGE_CODES.has(code)) {
    return `/static/images/Kohler/${code}.pdf.png`;
  }

  const productImage = (product.images && product.images[0]) || '';
  const suggestionImage = suggestion.image || '';

  const isPlaceholderOrPageExtracted = (value) => {
    const val = String(value || '').toLowerCase();
    if (val.includes('image_not_found') || val.includes('image not found')) return true;
    if ((val.includes('_p') && val.includes('_i')) || val.includes('page')) return true;
    return false;
  };

  // Only return a non-placeholder, non-page-extracted image
  if (productImage && !isPlaceholderOrPageExtracted(productImage)) return productImage;
  if (suggestionImage && !isPlaceholderOrPageExtracted(suggestionImage)) return suggestionImage;
  return ''; // No real image → frontend will show "No Image" box
}

export default function InlineSearch({ onAdd, disabled = false }) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [loading, setLoading] = useState(false);
  const [imageErrors, setImageErrors] = useState({});
  const [menuStyle, setMenuStyle] = useState(null);
  const [menuPlacement, setMenuPlacement] = useState('down');
  const [error, setError] = useState('');
  const suggestionRef = useRef(null);
  const inputRef = useRef(null);
  const menuRef = useRef(null);

  const resetSuggestions = () => {
    setSuggestions([]);
    setShowSuggestions(false);
    setLoading(false);
    setError('');
    setMenuStyle(null);
    setImageErrors({});
  };

  const markImgError = (src) => {
    if (!src) return;
    setImageErrors((prev) => (prev[src] ? prev : { ...prev, [src]: true }));
  };

  useEffect(() => {
    const handleClickOutside = (event) => {
      const clickedInsideField = suggestionRef.current && suggestionRef.current.contains(event.target);
      const clickedInsideMenu = menuRef.current && menuRef.current.contains(event.target);

      if (!clickedInsideField && !clickedInsideMenu) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (disabled) {
      setQuery('');
      resetSuggestions();
      return;
    }

    const trimmedQuery = query.trim();
    if (trimmedQuery.length < MIN_QUERY_LENGTH) {
      resetSuggestions();
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(() => {
      setLoading(true);
      setError('');
      setSuggestions([]);

      axios.get(`${BASE}/search-suggestions`, {
        params: { q: trimmedQuery, brand: 'all', limit: 50 },
        signal: controller.signal,
      })
        .then((res) => {
          if (controller.signal.aborted) {
            return;
          }

          const nextSuggestions = Array.isArray(res.data?.suggestions) ? res.data.suggestions : [];
          setSuggestions(nextSuggestions);
          setShowSuggestions(true);
        })
        .catch((err) => {
          if (controller.signal.aborted) {
            return;
          }

          console.error('Failed to load suggestions', err);
          setSuggestions([]);
          setError('Search suggestions unavailable. Please try again.');
          setShowSuggestions(true);
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setLoading(false);
          }
        });
    }, 250);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, disabled]);

  useEffect(() => {
    if (!showSuggestions || disabled || !inputRef.current) {
      setMenuStyle(null);
      return;
    }

    const updateMenuPosition = () => {
      if (!inputRef.current) {
        return;
      }

      const inputRect = inputRef.current.getBoundingClientRect();
      const estimatedMenuHeight = Math.min(menuRef.current?.scrollHeight || 280, MAX_MENU_HEIGHT);
      const spaceBelow = window.innerHeight - inputRect.bottom;
      const spaceAbove = inputRect.top;
      const nextPlacement = spaceBelow < estimatedMenuHeight + 24 && spaceAbove > spaceBelow ? 'up' : 'down';
      const nextWidth = Math.min(
        Math.max(inputRect.width, 260),
        window.innerWidth - VIEWPORT_PADDING * 2
      );
      const nextLeft = Math.min(
        Math.max(inputRect.left, VIEWPORT_PADDING),
        window.innerWidth - VIEWPORT_PADDING - nextWidth
      );
      const nextTop = nextPlacement === 'up'
        ? Math.max(VIEWPORT_PADDING, inputRect.top - estimatedMenuHeight - 10)
        : Math.min(
            window.innerHeight - VIEWPORT_PADDING - estimatedMenuHeight,
            inputRect.bottom + 10
          );

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
  }, [showSuggestions, disabled, loading, suggestions.length, error]);

  const internalAdd = (s) => {
    if (!s || disabled) return;

    // Pick full data from raw_item (now provided by backend)
    const product = s.raw_item || {};
    const sku = sanitizeDisplayText(product.sku || s.text || '').trim();
    const fullText = sanitizeDisplayText(
      product.display_text || product.text || s.full_name || s.description || s.text || ''
    );
    const firstLine = fullText.split('\n')[0].trim();
    const nameOnly = sanitizeDisplayText(
      product.display_name || product.name || firstLine || s.full_name || s.description || s.text || 'Product'
    );

    let cleanedNameOnly = stripProductCode(nameOnly);
    if (sku && cleanedNameOnly) {
      const norm = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
      const normSku = norm(sku);
      const normName = norm(cleanedNameOnly);
      if (normName === normSku || normSku.includes(normName) || normName.includes(normSku)) {
        cleanedNameOnly = '';
      }
    }

    const formatDisplayDescription = (rawText = '', skuVal = '') => {
      if (!rawText) return '';
      const cleanSku = String(skuVal || '').trim();
      const norm = (str) => str.toLowerCase().replace(/[^a-z0-9]/g, '');
      const normSku = norm(cleanSku);
      const linesList = String(rawText).split('\n');
      const cleanLines = [];

      for (let line of linesList) {
        let trimmed = line.trim();
        if (!trimmed) continue;
        if (norm(trimmed) === normSku) continue;

        trimmed = trimmed.replace(/mrp\s*(?:rs\.?|rs|INR|₹)?\s*[\d,\.\s`\/\-]*/gi, '');
        trimmed = trimmed.replace(/(?:rs\.?|rs|INR|₹)\s*[\d,\.\s`\/\-]*/gi, '');
        trimmed = trimmed.replace(/price\s*[\d,\.\s`\/\-]*/gi, '');

        if (cleanSku) {
          const escapeRegExp = (string) => string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
          const skuRegex = new RegExp(escapeRegExp(cleanSku), 'gi');
          trimmed = trimmed.replace(skuRegex, '');
        }
        // Safely remove only K- product codes and resulting empty brackets
        trimmed = trimmed.replace(/\bK-\d+[A-Z0-9\-]*\b/gi, '');
        trimmed = trimmed.replace(/\(\s*\)/g, '');
        trimmed = trimmed.replace(/\[\s*\]/g, '');
        trimmed = trimmed.replace(/[\s\-\,\.\(\[\)\]\+\/]+$/, '');
        trimmed = trimmed.replace(/^[\s\-\,\.\(\[\)\]\+\/]+/, '');
        trimmed = trimmed.replace(/\s+/g, ' ').trim();

        if (trimmed.length < 3) continue;
        if (!cleanLines.includes(trimmed)) {
          cleanLines.push(trimmed);
        }
      }
      return cleanLines.join('\n');
    };

    const cleanedFullText = formatDisplayDescription(fullText, sku);

    // Price extraction logic
    let finalPrice = product.price || '';
    if (product.variant_prices && Object.keys(product.variant_prices).length > 0) {
      const v = Object.keys(product.variant_prices)[0];
      finalPrice = product.variant_prices[v];
    }
    if (!finalPrice || finalPrice === '0') {
      const match = fullText.match(/MRP[^\d]*([\d,]+)/i);
      if (match) finalPrice = match[1].replace(/,/g, '');
    }

    const newItem = {
      name: cleanedNameOnly,
      price: String(finalPrice || '0'),
      quantity: 1,
      discount: 0,
      image: (() => {
        const forced = resolveSuggestionImage(product, s);
        return forced || null;
      })(),
      room: '',
      rawText: cleanedFullText,
      sku: sku,
      size: sanitizeDisplayText(product.size || ''),
    };

    console.log('ITEM READY TO ADD:', newItem);

    if (onAdd && typeof onAdd === 'function') {
      onAdd(newItem);
    } else {
      console.warn('onAdd PROP MISSING OR NOT A FUNCTION');
    }

    setQuery('');
    resetSuggestions();
  };

  const trimmedQuery = query.trim();
  const hasResults = suggestions.length > 0;
  const showMenu = !disabled && showSuggestions && trimmedQuery.length >= MIN_QUERY_LENGTH;

  const menuContent = showMenu ? (
    <div
      ref={menuRef}
      className="sp-suggestions-list"
      style={{
        ...menuStyle,
        maxHeight: `${MAX_MENU_HEIGHT}px`,
        overflowY: 'auto',
        padding: '0.75rem',
        position: 'fixed',
        zIndex: 15000,
        borderRadius: '1.25rem',
        border: '1px solid rgba(95, 99, 104, 0.22)',
        borderTop: menuPlacement === 'up' ? '1px solid rgba(95, 99, 104, 0.22)' : '4px solid var(--primary-color)',
        borderBottom: menuPlacement === 'up' ? '4px solid var(--primary-color)' : '1px solid rgba(95, 99, 104, 0.22)',
        background: 'var(--surface-color)',
        color: 'var(--text-primary)',
        boxShadow: '0 30px 60px -28px rgba(0, 0, 0, 0.65)',
        backdropFilter: 'blur(18px)',
        WebkitBackdropFilter: 'blur(18px)',
      }}
    >
      {loading && (
        <div
          style={{
            padding: '0.85rem 0.95rem',
            borderRadius: '0.9rem',
            border: '1px solid rgba(95, 99, 104, 0.16)',
            background: 'var(--bg-color)',
            color: 'var(--text-secondary)',
            fontSize: '0.9rem',
            fontWeight: 700,
          }}
        >
          Searching suggestions...
        </div>
      )}

      {!loading && error && (
        <div
          style={{
            padding: '0.85rem 0.95rem',
            borderRadius: '0.9rem',
            border: '1px solid rgba(248, 113, 113, 0.22)',
            background: 'rgba(248, 113, 113, 0.08)',
            color: '#fecaca',
            fontSize: '0.9rem',
            fontWeight: 700,
          }}
        >
          {error}
        </div>
      )}

      {!loading && !error && !hasResults && (
        <div
          style={{
            padding: '0.85rem 0.95rem',
            borderRadius: '0.9rem',
            border: '1px dashed rgba(95, 99, 104, 0.3)',
            background: 'var(--bg-color)',
            color: 'var(--text-secondary)',
            fontSize: '0.9rem',
            fontWeight: 600,
          }}
        >
          No suggestions found for "{trimmedQuery}".
        </div>
      )}

      {!loading && !error && hasResults && suggestions.map((s, idx) => (
        <div
          key={
            s?.raw_item?.search_code
            || s?.raw_item?.name
            || s?.full_name
            || s?.text
            || idx
          }
          className="sp-suggestion-item"
          onMouseDown={(e) => {
            e.preventDefault();
            internalAdd(s);
          }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '10px 12px',
            cursor: 'pointer',
            borderRadius: '12px',
            border: '1px solid rgba(95, 99, 104, 0.12)',
            background: 'var(--bg-color)',
            marginBottom: idx === suggestions.length - 1 ? 0 : '8px',
            transition: 'transform 0.2s ease, background-color 0.2s ease, border-color 0.2s ease',
          }}
        >
          <SuggestionThumbnail suggestion={s} product={s.raw_item || {}} />

          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontWeight: 800,
                color: 'var(--text-primary)',
                lineHeight: 1.35,
                whiteSpace: 'normal',
                overflowWrap: 'anywhere',
                fontSize: '1rem',
              }}
            >
              {sanitizeDisplayText(s.display_code || s.text || 'Product')}
            </div>
            <div
              style={{
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                marginTop: '0.2rem',
                lineHeight: 1.4,
                whiteSpace: 'normal',
                overflowWrap: 'anywhere',
              }}
            >
              {sanitizeDisplayText(s.description || stripProductCode(s.display_name || s.full_name))}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', flexShrink: 0 }}>
            <div
              style={{
                fontSize: '0.68rem',
                color: 'var(--primary-color)',
                fontWeight: 800,
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0.45rem 0.75rem',
                borderRadius: '999px',
                border: '1px solid var(--primary-color)',
                background: 'rgba(99, 102, 241, 0.05)',
                whiteSpace: 'nowrap'
              }}
            >
              {sanitizeDisplayText(s.brand || 'Catalog').toUpperCase()}
            </div>
            <div
              style={{
                fontSize: '0.9rem',
                fontWeight: 800,
                color: s.price ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontFamily: 'var(--font-mono, monospace)',
                opacity: s.price ? 1 : 0.6
              }}
            >
              {s.price ? `₹${s.price}` : 'No Price'}
            </div>
          </div>
        </div>
      ))}
    </div>
  ) : null;

  return (
    <div style={{ position: 'relative', width: '100%' }} ref={suggestionRef}>
      <form
        style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
        onSubmit={(e) => {
          e.preventDefault();
          if (suggestions.length > 0) {
            internalAdd(suggestions[0]);
          }
        }}
      >
        <input
          ref={inputRef}
          className="sp-search-input"
          style={{
            flex: 1,
            padding: '0.7rem 1rem',
            borderRadius: '1rem',
            border: '1px solid #ddd',
            outline: 'none',
            fontSize: '0.9rem',
          }}
          placeholder="Search Product e.g. 4000 or Rain Shower"
          value={query}
          autoComplete="off"
          disabled={disabled}
          onFocus={() => {
            if (query.trim().length >= MIN_QUERY_LENGTH && (suggestions.length > 0 || loading || error)) {
              setShowSuggestions(true);
            }
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setShowSuggestions(true);
            setError('');
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setShowSuggestions(false);
            }
          }}
        />
        <button
          type="submit"
          style={{
            padding: '0.7rem 1.4rem',
            borderRadius: '1rem',
            background: 'var(--primary-gradient)',
            color: 'var(--primary-color)',
            border: 'none',
            cursor: 'pointer',
            fontWeight: '900',
            fontSize: '0.85rem',
          }}
          disabled={loading || disabled}
        >
          {loading ? '...' : disabled ? 'VIEW' : 'ADD'}
        </button>
      </form>

      {typeof document !== 'undefined' && menuContent
        ? createPortal(menuContent, document.body)
        : null}
    </div>
  );
}
