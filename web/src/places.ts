/**
 * Display table for Alberta place names: values are shown proper-cased ("Calgary", never "calgary")
 * whatever case they were typed or extracted in. Display only; stored values are untouched.
 */
const PLACES = [
  "Alberta",
  "Calgary",
  "Edmonton",
  "Red Deer",
  "Lethbridge",
  "Medicine Hat",
  "Grande Prairie",
  "Airdrie",
  "St. Albert",
  "Spruce Grove",
  "Leduc",
  "Fort Saskatchewan",
  "Okotoks",
  "Cochrane",
  "Canmore",
  "Banff",
  "Camrose",
  "Lloydminster",
  "Brooks",
  "Wetaskiwin",
  "Fort McMurray",
  "Wood Buffalo",
  "Strathcona County",
  "Sherwood Park",
  "Rocky View County",
  "Foothills County",
  "Parkland County",
];

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const PATTERN = new RegExp(`\\b(${PLACES.map(escape).join("|")})(?![\\w])`, "gi");
const BY_LOWER = new Map(PLACES.map((p) => [p.toLowerCase(), p]));

export const properPlaces = (text: string) => text.replace(PATTERN, (m) => BY_LOWER.get(m.toLowerCase()) ?? m);
