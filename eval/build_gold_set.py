"""Build eval/gold_set.jsonl — one labeled conversation per line."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "gold_set.jsonl"

# (text, relevant, outcome_stance, primary_barrier)
ROWS: list[tuple[str, bool, str, str]] = [
    # A — bookmark / intent
    ("I wishlist looks on Myntra just for outfit inspiration, not buying this month.", True, "bookmark_only", "bookmark_inspiration"),
    ("Saved 40 dresses to my wishlist as a mood board for later styling ideas.", True, "bookmark_only", "bookmark_inspiration"),
    ("I keep AJIO wishlist for Pinterest-style looks, never check out.", True, "bookmark_only", "bookmark_inspiration"),
    ("Added to wishlist to compare later with other brands before deciding.", True, "postpone", "bookmark_compare_later"),
    ("Shortlisted three kurtis so I can compare fabric and price next weekend.", True, "postpone", "bookmark_compare_later"),
    ("Wishlist is for my sister's birthday gift ideas, not for me.", True, "bookmark_only", "gift_or_other_person"),
    ("Saved this for Mum — she might like it, I won't buy for myself.", True, "bookmark_only", "gift_or_other_person"),
    ("Maybe I'll buy someday, no rush, just sitting in wishlist.", True, "bookmark_only", "low_urgency_maybe"),
    ("Low priority wishlist dump — if I remember maybe next sale.", True, "unclear", "low_urgency_maybe"),
    # B — fit / uncertainty
    ("Added to wishlist but scared to order — Myntra size chart never matches my body.", True, "postpone", "fit_size_uncertainty"),
    ("Love the dress but size S/M confusion, leaving it wishlisted until I know fit.", True, "postpone", "fit_size_uncertainty"),
    ("Waiting to see a haul on my body type before I buy from wishlist.", True, "postpone", "fit_size_uncertainty"),
    ("AJIO sizing is random so I wishlist and never convert until I find similar-body reviews.", True, "postpone", "fit_size_uncertainty"),
    ("Photos look great but I'm sure the real fabric will disappoint — still on wishlist.", True, "abandon", "looks_vs_reality"),
    ("Wishlisted because studio photos look fake; need real customer pics first.", True, "postpone", "looks_vs_reality"),
    ("Not sure this kurti works with my wardrobe so it's stuck in wishlist.", True, "postpone", "styling_wardrobe_fit"),
    ("Saved for a wedding later this year — wrong occasion timing to buy now.", True, "postpone", "occasion_timing"),
    ("Waiting for Diwali week before buying the wishlisted lehenga.", True, "postpone", "occasion_timing"),
    ("Won't buy until friends say it looks good on me — still wishlisted.", True, "postpone", "social_validation"),
    ("Need Instagram opinions before converting this wishlist save.", True, "postpone", "social_validation"),
    # C — price / value
    ("Waiting for 50% off — MRP looks fake so I just wishlist.", True, "postpone", "wait_for_price_drop"),
    ("I'll buy when there's a real coupon, not 10% off on my wishlist item.", True, "postpone", "wait_for_price_drop"),
    ("Price watch on Myntra wishlist until Big Billion / End of Reason sale.", True, "postpone", "wait_for_price_drop"),
    ("Found cheaper on another site so leaving Myntra wishlist alone.", True, "abandon", "better_price_elsewhere"),
    ("Same dress cheaper on AJIO; Myntra wishlist is just for tracking.", True, "abandon", "better_price_elsewhere"),
    ("Waiting for payday to clear my wishlist checkout.", True, "postpone", "budget_payday"),
    ("Salary next week — wishlist stays until then.", True, "postpone", "budget_payday"),
    ("Not convinced the quality matches the price so I won't buy yet.", True, "postpone", "value_doubt"),
    ("Wishlisted but value seems poor for what they charge.", True, "abandon", "value_doubt"),
    # D — trust / returns
    ("Returns are a pain so I just leave it in wishlist instead of ordering.", True, "abandon", "return_exchange_friction"),
    ("Exchange pickup hassle keeps me from buying wishlisted shoes.", True, "postpone", "return_exchange_friction"),
    ("Don't trust the reviews on this PDP — staying wishlisted.", True, "postpone", "review_trust"),
    ("Fake reviews vibe; won't convert wishlist until better proof.", True, "abandon", "review_trust"),
    ("Had a bad past order from this seller so wishlist only, no buy.", True, "abandon", "past_bad_experience"),
    ("Last return experience was awful — wishlist is safer than ordering.", True, "abandon", "past_bad_experience"),
    ("Worried about authenticity on marketplace sellers — wishlisted not bought.", True, "postpone", "counterfeit_or_seller_doubt"),
    ("Seller rating looks shady; keeping the dress in wishlist only.", True, "abandon", "counterfeit_or_seller_doubt"),
    # E — comparison
    ("Too many items shortlisted — decision paralysis, buy nothing.", True, "postpone", "too_many_shortlisted"),
    ("Wishlist has 80 pieces and I freeze every time I open it.", True, "bookmark_only", "too_many_shortlisted"),
    ("Can't compare sizes and delivery side by side so wishlist sits.", True, "postpone", "missing_compare_tools"),
    ("App needs a proper compare for shortlist — until then no buy.", True, "postpone", "missing_compare_tools"),
    ("Bought from Zara instead of converting my Myntra wishlist.", True, "abandon", "switched_to_alternative"),
    ("Ended up ordering elsewhere; wishlist item abandoned.", True, "abandon", "switched_to_alternative"),
    # F — ops
    ("My size went OOS after I wishlisted — can't buy now.", True, "abandon", "oos_after_wishlist"),
    ("Wishlisted color disappeared from stock, so no purchase.", True, "abandon", "oos_after_wishlist"),
    ("Delivery would miss the wedding date so I left it wishlisted.", True, "abandon", "delivery_too_slow"),
    ("Shipping ETA too slow for the event — wishlist only.", True, "postpone", "delivery_too_slow"),
    ("COD failed at checkout for my wishlisted dress again.", True, "abandon", "payment_or_app_friction"),
    ("App keeps crashing at payment so wishlist never converts.", True, "abandon", "payment_or_app_friction"),
    ("Forgot my wishlist for months — everything feels stale now.", True, "abandon", "forgotten_wishlist"),
    ("No reminders; wishlist went cold and I moved on.", True, "abandon", "forgotten_wishlist"),
    # G — off platform
    ("Still watching YouTube hauls before buying from my wishlist.", True, "postpone", "seeking_external_proof"),
    ("Need Reddit fit advice before converting this save.", True, "postpone", "seeking_external_proof"),
    ("Waiting for Instagram try-on videos for this exact SKU.", True, "postpone", "seeking_external_proof"),
    # more seed coverage
    ("Size chart says M but reviews say size up — wishlist stall.", True, "postpone", "fit_size_uncertainty"),
    ("Keeping it wishlisted until End of Reason Sale discount is real.", True, "postpone", "wait_for_price_drop"),
    ("Inspiration save only — never planned to checkout.", True, "bookmark_only", "bookmark_inspiration"),
    ("Compare later with Nykaa Fashion prices before I decide.", True, "postpone", "bookmark_compare_later"),
    ("Gift shortlist for cousin, not my purchase intent.", True, "bookmark_only", "gift_or_other_person"),
    ("Looks vs reality gap — fabric will be shiny, leaving wishlist.", True, "abandon", "looks_vs_reality"),
    ("Doesn't match my office wardrobe so wishlist forever.", True, "postpone", "styling_wardrobe_fit"),
    ("Buying after festival season when I actually need it.", True, "postpone", "occasion_timing"),
    ("Need coworkers to validate the look first.", True, "postpone", "social_validation"),
    ("Amazon IN has better deal than my AJIO wishlist price.", True, "abandon", "better_price_elsewhere"),
    ("Budget tight until month end — wishlist holds.", True, "postpone", "budget_payday"),
    ("Quality doubt at this MRP; won't convert.", True, "abandon", "value_doubt"),
    ("Return window too short; scared to order from wishlist.", True, "postpone", "return_exchange_friction"),
    ("Reviews contradict each other — trust issue, wishlist only.", True, "postpone", "review_trust"),
    ("Seller changed after cart; authenticity worry.", True, "abandon", "counterfeit_or_seller_doubt"),
    ("Shortlist overload — pick none.", True, "postpone", "too_many_shortlisted"),
    ("No compare tool for fabric GSM — stuck.", True, "postpone", "missing_compare_tools"),
    ("Switched to local boutique instead of wishlist checkout.", True, "abandon", "switched_to_alternative"),
    ("Size XL vanished after wishlist — OOS block.", True, "abandon", "oos_after_wishlist"),
    ("Courier too slow for trip next week.", True, "abandon", "delivery_too_slow"),
    ("UPI fails every time on this app checkout.", True, "abandon", "payment_or_app_friction"),
    ("Rediscovered old wishlist — already bought elsewhere months ago.", True, "abandon", "forgotten_wishlist"),
    ("Reading Reddit threads before I tap buy on wishlisted sneakers.", True, "postpone", "seeking_external_proof"),
    ("Myntra wishlist used as lookbook for college outfits.", True, "bookmark_only", "bookmark_inspiration"),
    ("Will buy after next coupon drop email.", True, "postpone", "wait_for_price_drop"),
    ("Fit uncertainty on jeans — need try-on video.", True, "postpone", "fit_size_uncertainty"),
    ("Past dye-bleed issue with brand; won't reorder from wishlist.", True, "abandon", "past_bad_experience"),
    ("Waiting for bank credit — payday barrier.", True, "postpone", "budget_payday"),
    ("Photoshoot lighting lies; reality check needed.", True, "postpone", "looks_vs_reality"),
    ("Wishlist compare later with sister's picks.", True, "postpone", "bookmark_compare_later"),
    ("Out of stock after sale alert — missed buy.", True, "abandon", "oos_after_wishlist"),
    ("App checkout OTP loop — friction.", True, "abandon", "payment_or_app_friction"),
    ("Forgotten list from last year still sitting there.", True, "abandon", "forgotten_wishlist"),
    ("Seeking external proof on length before purchase.", True, "postpone", "seeking_external_proof"),
    ("Return pickup never came last time — friction high.", True, "abandon", "return_exchange_friction"),
    ("Value doubt on embroidered set at this price.", True, "postpone", "value_doubt"),
    ("Gift for Diwali guest — not self purchase intent.", True, "bookmark_only", "gift_or_other_person"),
    ("Maybe later if I still like it — low urgency.", True, "unclear", "low_urgency_maybe"),
    ("Social validation from roommate before buy.", True, "postpone", "social_validation"),
    ("Styling wardrobe fit unclear with existing tops.", True, "postpone", "styling_wardrobe_fit"),
    ("Occasion is months away — timing wait.", True, "postpone", "occasion_timing"),
    ("Better price elsewhere on same SKU code.", True, "abandon", "better_price_elsewhere"),
    ("Counterfeit fear on marketplace listing.", True, "postpone", "counterfeit_or_seller_doubt"),
    ("Too many shortlisted ethnic sets — paralysis.", True, "postpone", "too_many_shortlisted"),
    ("Missing compare for sleeve length across shortlist.", True, "postpone", "missing_compare_tools"),
    ("Switched to alternative brand sale overnight.", True, "abandon", "switched_to_alternative"),
    ("Delivery too slow for tomorrow's event.", True, "abandon", "delivery_too_slow"),
    ("Review trust broken after sponsored-looking 5-stars.", True, "abandon", "review_trust"),
    # irrelevant controls (~15%)
    ("The weather in Goa is nice this week and I like mangoes a lot.", False, "unclear", "other_offtopic"),
    ("Who won the cricket match yesterday? Score was crazy.", False, "unclear", "other_offtopic"),
    ("Recipe for dal makhani please, no shopping talk.", False, "unclear", "other_offtopic"),
    ("My phone battery drains too fast after the update.", False, "unclear", "other_offtopic"),
    ("Looking for Python tutorial on FastAPI beginners.", False, "unclear", "other_offtopic"),
    ("Traffic on the highway was terrible this morning.", False, "unclear", "other_offtopic"),
    ("Concert tickets sold out in minutes again.", False, "unclear", "other_offtopic"),
    ("Dog training tips for puppies that bite furniture.", False, "unclear", "other_offtopic"),
    ("Stock market dipped; holding my mutual funds.", False, "unclear", "other_offtopic"),
    ("Best cafes in Indiranagar for remote work?", False, "unclear", "other_offtopic"),
    ("How do I reset my WiFi router password?", False, "unclear", "other_offtopic"),
    ("Movie recommendations for a rainy Sunday.", False, "unclear", "other_offtopic"),
    ("Gym PR on deadlifts today felt great.", False, "unclear", "other_offtopic"),
    ("Plant care for indoor monstera yellowing leaves.", False, "unclear", "other_offtopic"),
    ("Flight delayed three hours at the airport.", False, "unclear", "other_offtopic"),
]


def main() -> None:
    assert 80 <= len(ROWS) <= 150, len(ROWS)
    lines = []
    for i, (text, relevant, stance, barrier) in enumerate(ROWS, start=1):
        lines.append(
            json.dumps(
                {
                    "id": f"gold-{i:03d}",
                    "text": text,
                    "relevant": relevant,
                    "outcome_stance": stance,
                    "primary_barrier": barrier,
                },
                ensure_ascii=False,
            )
        )
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} rows to {OUT}")


if __name__ == "__main__":
    main()
