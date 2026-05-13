import { useState, useRef, useEffect } from 'react';

/**
 * Multi-select dropdown. Options are { id, name }. value: array of selected ids. onChange(ids).
 */
export function MultiSelect({
  options = [],
  value = [],
  onChange,
  placeholder = 'Select...',
  disabled,
  maxSelected = null,
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const safeOptions = Array.isArray(options) ? options : [];
  const safeValue = Array.isArray(value) ? value : [];

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const toggle = (id) => {
    if (safeValue.includes(id)) onChange(safeValue.filter((v) => v !== id));
    else if (maxSelected != null && safeValue.length >= maxSelected) return;
    else onChange([...safeValue, id]);
  };

  const remove = (e, id) => {
    e.stopPropagation();
    onChange(safeValue.filter((v) => v !== id));
  };

  const selected = safeOptions.filter((o) => safeValue.includes(o.id));

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => !disabled && setOpen((o) => !o)}
        disabled={disabled}
        className="flex items-center justify-between w-full min-h-[40px] py-2 px-3 rounded-lg border border-gray-300 bg-white hover:bg-gray-50 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 outline-none text-left transition-colors disabled:opacity-50"
      >
        <div className="flex flex-wrap gap-1 flex-1">
          {selected.length === 0 ? (
            <span className="text-gray-400 text-sm">{placeholder}</span>
          ) : (
            selected.map((item) => (
              <span
                key={item.id}
                className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 px-2 py-0.5 rounded-md text-sm"
              >
                {item.name}
                <button type="button" onClick={(e) => remove(e, item.id)} className="hover:text-blue-900" aria-label="Remove">×</button>
              </span>
            ))
          )}
        </div>
        <span className="ml-2 text-gray-400">▼</span>
      </button>
      {open && (
        <div className="absolute z-10 w-full mt-1 py-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-64 overflow-auto">
          {safeOptions.map((opt) => (
            <label key={opt.id} className="flex items-center gap-2 px-3 py-2 hover:bg-gray-100 cursor-pointer">
              <input
                type="checkbox"
                checked={safeValue.includes(opt.id)}
                onChange={() => toggle(opt.id)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm">{opt.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
