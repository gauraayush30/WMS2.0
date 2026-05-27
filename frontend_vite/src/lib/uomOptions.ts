export interface UomOption {
  value: string;
  label: string;
}

export const UOM_OPTIONS: UomOption[] = [
  // Count
  { value: "pcs", label: "pcs – Pieces" },
  { value: "unit", label: "unit – Units" },
  { value: "pair", label: "pair – Pairs" },
  { value: "dozen", label: "dozen – Dozens" },
  { value: "box", label: "box – Boxes" },
  { value: "carton", label: "carton – Cartons" },
  { value: "pack", label: "pack – Packs" },
  { value: "set", label: "set – Sets" },
  // Weight
  { value: "kg", label: "kg – Kilograms" },
  { value: "g", label: "g – Grams" },
  { value: "mg", label: "mg – Milligrams" },
  { value: "lb", label: "lb – Pounds" },
  { value: "oz", label: "oz – Ounces" },
  { value: "ton", label: "ton – Metric Tons" },
  // Volume
  { value: "l", label: "l – Litres" },
  { value: "ml", label: "ml – Millilitres" },
  { value: "gal", label: "gal – Gallons" },
  { value: "fl oz", label: "fl oz – Fluid Ounces" },
  // Length / Area
  { value: "m", label: "m – Metres" },
  { value: "cm", label: "cm – Centimetres" },
  { value: "mm", label: "mm – Millimetres" },
  { value: "ft", label: "ft – Feet" },
  { value: "in", label: "in – Inches" },
  { value: "sqm", label: "sqm – Square Metres" },
  // Other
  { value: "roll", label: "roll – Rolls" },
];
