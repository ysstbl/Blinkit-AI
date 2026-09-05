import React from 'react';

export default function ProductCard({ name, weight, price, imagePlaceholder }) {
  return (
    <div className="bg-white rounded-xl p-3 border border-gray-100 shadow-[0_1px_4px_rgba(0,0,0,0.05)] flex flex-col h-full relative">
      <div className="bg-gray-50 rounded-lg h-24 mb-3 flex items-center justify-center text-xs text-gray-400">
        {imagePlaceholder || "Image"}
      </div>
      
      <div className="flex-1">
        <h3 className="text-[13px] font-medium leading-tight line-clamp-2 text-blinkit-text mb-1">
          {name}
        </h3>
        <p className="text-xs text-blinkit-muted mb-3">{weight}</p>
      </div>

      <div className="flex justify-between items-center mt-auto">
        <span className="font-semibold text-sm">₹{price}</span>
        <button className="border border-blinkit-green text-blinkit-green bg-green-50/50 hover:bg-blinkit-green hover:text-white px-4 py-1.5 rounded-lg text-xs font-bold uppercase tracking-wide transition-colors">
          Add
        </button>
      </div>
    </div>
  );
}