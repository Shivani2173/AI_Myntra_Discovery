export type BehaviorCard = {
  id: string;
  title: string;
  didntBuyPct: number;
  n: number;
  voices: number;
  whatTheyDo: string;
  postponePct: number;
  abandonPct: number;
  bookmarkPct: number;
  sources: { reddit: number; youtube: number; appStore: number };
  oftenWith: string[];
  stage: string;
  intensity: number;
  quotes: string[];
};

export const STUB_HEADER = {
  analyzed: 847,
  voices: 612,
  bookmarkPct: 22,
  postponePct: 51,
  abandonPct: 27,
  lastSaved: "Phase 0 stub — not live data",
  caption: "Of analyzed wishlist conversations, not Myntra live conversion.",
};

export const STUB_BEHAVIORS: BehaviorCard[] = [
  {
    id: "price-wait",
    title: "Waiting for a “real” discount",
    didntBuyPct: 24,
    n: 203,
    voices: 156,
    whatTheyDo:
      "Keep it wishlisted as a price alert until a sale or coupon feels honest vs MRP.",
    postponePct: 78,
    abandonPct: 9,
    bookmarkPct: 13,
    sources: { reddit: 61, youtube: 10, appStore: 29 },
    oftenWith: ["value doubt", "forgotten list"],
    stage: "wait",
    intensity: 3.4,
    quotes: [
      "Waiting for 50% off — MRP looks fake so I just wishlist.",
      "I’ll buy when there’s a real coupon, not 10% off.",
    ],
  },
  {
    id: "size-fit",
    title: "Like the look, don’t trust the size",
    didntBuyPct: 18,
    n: 152,
    voices: 119,
    whatTheyDo:
      "Product is already chosen; they stall until similar-body photos or a trusted size chart.",
    postponePct: 61,
    abandonPct: 24,
    bookmarkPct: 15,
    sources: { reddit: 48, youtube: 37, appStore: 15 },
    oftenWith: ["looks vs reality", "return hassle"],
    stage: "evaluate",
    intensity: 4.1,
    quotes: [
      "Added to wishlist but scared to order — Myntra size chart never matches.",
      "Waiting to see a haul on my body type before I buy.",
    ],
  },
  {
    id: "lookbook",
    title: "Wishlist is a lookbook, not a cart",
    didntBuyPct: 16,
    n: 136,
    voices: 101,
    whatTheyDo: "Save outfits for inspiration with no wear plan.",
    postponePct: 14,
    abandonPct: 5,
    bookmarkPct: 81,
    sources: { reddit: 88, youtube: 12, appStore: 0 },
    oftenWith: ["low urgency"],
    stage: "save",
    intensity: 2.1,
    quotes: ["I wishlist looks I like, not things I’m buying this month."],
  },
];
