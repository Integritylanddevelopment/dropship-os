"""Cluster similar product signals into one 'product opportunity'.

Cheap deterministic clusterer: token-set Jaccard similarity on normalized titles.
Better than nothing without embeddings, and zero external deps."""
import re
from collections import Counter

STOP = set("""
a an the of for and or to in on with from this that is are was were be been being
it its they them we us you your i my me mine our he she his her him
do did does done doing will would could should can may might shall
have has had having get got gets getting
not no nor but so yet just also very too much more most even still
all any some each every few many more most other another such
what which who whom whose when where why how
here there then than very really actually basically literally just
about after again against between through during before above below
up down out off over under new old big small great good bad best worst
first last next only own same few little less least
want need like know think see look find take make go come say tell give
use try keep let put run set turn move call ask seem show hear help
one two three four five
now well back way even because since while though although however
thing things people something someone everyone anyone
right left top bottom
going gonna wanna
lol lmao omg wtf idk imo imho tbh fwiw
post thread sub comment reply upvote downvote karma
reddit redditor subreddit
hey guys anyone else
looking bought found love hate
f4m m4f m4m f4f r4r
""".split())

# Product-relevant terms that should NOT be stopped
PRODUCT_TERMS = set("""
led light lights lamp bulb strip neon
kitchen gadget tool utensil knife
pet dog cat collar leash bowl feeder toy
fitness gym workout yoga resistance band
posture corrector brace support
home decor pillow blanket rug
phone case charger holder mount stand
water bottle flask cup mug
bag backpack wallet purse
beauty skin care serum cream mask
hair brush comb dryer straightener
organizer storage shelf rack hook
mat pad cushion foam
speaker headphone earbuds wireless bluetooth
watch clock timer alarm
plant pot planter garden
massage gun roller ball
cleaner vacuum mop spray
camera tripod ring selfie
pen marker notebook journal
soap dispenser towel holder
mirror magnifying
scale thermometer
umbrella raincoat
fan heater humidifier
wellness sauna therapy sleep tracker compression patch
insole knee wrist ankle elbow shoulder
diffuser aromatherapy essential oil
yard sprinkler hose mower trimmer rake shovel
grill firepit patio deck birdhouse
tent tarp lantern flashlight headlamp binoculars
camping hammock cooler thermos canteen
decoy camo blind stand rangefinder
fishing lure rod reel tackle
bike helmet gloves goggles
stroller carrier crib bassinet
blender juicer airfryer skillet
humidifier purifier dehumidifier
doormat curtain blinds
keychain lanyard carabiner
""".split())

# Words that are NEVER valid product keywords on their own
KEYWORD_JUNK = set("""
wrong tried bunch dropshipping shopify amazon ebay etsy tiktok reddit
apple google pay cash app store online shipping free sale deal
review reviews rating unboxing haul favorite favorites
question advice suggestion recommendation experience story
update news today yesterday week month year daily
guys folks everyone people person friend family
work works working worked school job money price cost
issue problem broken fixed error fail
happy sad angry funny weird crazy cool nice
america american usa china chinese
temu coupon coupons promo wish alibaba
nerd nerdy geek fell girl guy woman man
f4a f4m m4a a4a activities tips learn
selling buying trading pick picks
rtx gpu nvidia amd intel ps5 xbox
""".split())


def _is_valid_keyword(kw: str, titles: list[str]) -> bool:
    """A usable product keyword is a bigram, a known product term, or a
    substantial token that appears across multiple signal titles."""
    if not kw:
        return False
    parts = kw.split()
    if any(p in KEYWORD_JUNK for p in parts):
        return False
    if len(parts) >= 2:
        return True  # bigrams are usually real product phrases
    tok = parts[0]
    if tok in PRODUCT_TERMS:
        return True
    if len(tok) < 5:
        return False
    hits = sum(1 for t in titles if tok in t.lower())
    return hits >= 2


def _tokenize(s: str) -> set[str]:
    if not s:
        return set()
    words = re.findall(r"[a-z0-9]+", s.lower())
    return {w for w in words if w not in STOP and len(w) > 2}


def _jaccard(a: set, b: set) -> float:
    if not a or not b: return 0.0
    return len(a & b) / len(a | b)


def cluster(signals: list[dict], min_similarity: float = 0.35) -> list[list[dict]]:
    """Greedy single-link cluster on title-token Jaccard. Returns list of signal-lists."""
    tokens = [_tokenize((s.get("title") or "") + " " + " ".join(s.get("tags") or [])) for s in signals]
    clusters: list[list[int]] = []
    cluster_tokens: list[set] = []
    for i, tk in enumerate(tokens):
        placed = False
        for ci, ctk in enumerate(cluster_tokens):
            if _jaccard(tk, ctk) >= min_similarity:
                clusters[ci].append(i)
                cluster_tokens[ci] = ctk | tk
                placed = True
                break
        if not placed:
            clusters.append([i])
            cluster_tokens.append(tk)
    return [[signals[i] for i in c] for c in clusters]


def cluster_keyword(cluster_signals: list[dict]) -> str:
    """Extract a representative product keyword from a cluster.

    Strategy:
    1. Prefer known product terms from PRODUCT_TERMS
    2. Build bigrams from titles for multi-word product names
    3. Fall back to most common non-stop token if no product terms found
    """
    all_tokens = []
    bigrams = []

    for s in cluster_signals:
        title = s.get("title") or ""
        words = re.findall(r"[a-z0-9]+", title.lower())
        clean = [w for w in words if w not in STOP and len(w) > 2]
        all_tokens.extend(clean)

        # Build bigrams from cleaned words
        for i in range(len(clean) - 1):
            bigrams.append(f"{clean[i]} {clean[i+1]}")

    if not all_tokens:
        return ""

    # 1. Check for known product terms
    product_hits = [t for t in all_tokens if t in PRODUCT_TERMS]
    if product_hits:
        # Find the most common product term
        counts = Counter(product_hits)
        best_term = counts.most_common(1)[0][0]

        # Try to find a bigram containing this term for a better keyword
        related_bigrams = [b for b in bigrams if best_term in b.split()]
        if related_bigrams:
            bg_counts = Counter(related_bigrams)
            best_bigram = bg_counts.most_common(1)[0][0]
            if bg_counts[best_bigram] >= 2:
                return best_bigram
        return best_term

    # 2. Try bigrams - prefer repeated multi-word phrases
    if bigrams:
        bg_counts = Counter(bigrams)
        best_bg, best_count = bg_counts.most_common(1)[0]
        if best_count >= 2:
            return best_bg

    # 3. Fallback: most common meaningful token (min 4 chars to avoid junk)
    counts = Counter(all_tokens)
    # Prefer longer tokens as they're more likely to be product-relevant
    scored = [(tok, cnt, len(tok)) for tok, cnt in counts.items() if len(tok) >= 4]
    if scored:
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return scored[0][0]

    # Last resort
    return counts.most_common(1)[0][0]
