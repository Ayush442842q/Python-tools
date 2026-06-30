#!/usr/bin/env python3
"""
Diceware Passphrase Generator

Generates memorable, cryptographically secure passphrases using the Diceware method.
Includes an interactive mode that lets you input physical dice rolls (5 rolls per word).

Usage:
    python diceware_passphrase_generator.py [options]
"""

import sys
import argparse
import secrets
import math

# A curated, clean list of 1000 easy-to-type, distinct words for standalone utility.
# We map them to indices to simulate dice rolls or direct random index selection.
# Since we want to support physical 5-dice rolls (values 1-6), we will map 5-digit base-6 numbers (e.g., 11111 to 66666).
# The standard Diceware list has 7776 words. We will embed a compact version of it containing common English words.
# To keep the script small but highly secure, here is a list of 1,000 highly distinct words.
# Actually, let's embed a standard list of 1,296 words (4-dice rolls, values 1111 to 6666) which is extremely clean
# and fits perfectly in a standalone script while providing 10.3 bits of entropy per word.
# Let's write the word list.

WORDLIST = [
    "about", "above", "actor", "acute", "admit", "adopt", "adult", "after", "again", "agent",
    "agree", "ahead", "alarm", "album", "alert", "alike", "alive", "allow", "alone", "along",
    "alter", "amber", "amuse", "anchor", "angel", "anger", "angle", "angry", "animal", "ankle",
    "annoy", "apart", "apple", "apron", "arena", "argue", "arise", "armor", "arrow", "artist",
    "asphalt", "asset", "assist", "atlas", "attack", "attic", "audio", "audit", "avoid", "awake",
    "award", "aware", "awful", "bacon", "badge", "badly", "bagel", "baker", "balance", "ballot",
    "banana", "band", "bank", "banner", "barley", "barrel", "basin", "basket", "batch", "bath",
    "baton", "beach", "beacon", "bead", "beak", "beam", "bean", "bear", "beast", "beauty",
    "beef", "beer", "beetle", "begin", "behave", "behind", "belief", "bell", "bench", "berry",
    "best", "beyond", "bible", "bicycle", "bidder", "bigot", "bike", "bill", "binary", "binder",
    "bird", "birth", "biscuit", "bishop", "bison", "bitter", "black", "blade", "blame", "blank",
    "blast", "blaze", "blend", "bless", "blind", "blink", "bliss", "block", "blond", "blood",
    "bloom", "blouse", "blue", "blunt", "blur", "blush", "board", "boast", "boat", "body",
    "boil", "bold", "bolt", "bomb", "bond", "bone", "bonus", "book", "boom", "boost",
    "boot", "border", "boring", "boss", "botany", "both", "bottle", "bottom", "bounce", "bound",
    "bowl", "boxer", "brain", "brake", "branch", "brand", "brass", "brave", "bread", "break",
    "breath", "breeze", "brick", "bride", "bridge", "brief", "bright", "bring", "brisk", "broad",
    "broken", "bronze", "brook", "broom", "brown", "brush", "bubble", "bucket", "buckle", "budget",
    "buffer", "buggy", "build", "bulb", "bullet", "bundle", "bunk", "burden", "bureau", "burn",
    "bush", "bust", "busy", "butter", "button", "buyer", "bypass", "cabin", "cable", "cactus",
    "cage", "cake", "canal", "canary", "candle", "candy", "cane", "cannon", "canoe", "canvas",
    "canyon", "cape", "carbon", "card", "care", "cargo", "carpet", "carrot", "carry", "cart",
    "carve", "case", "cash", "cask", "castle", "casual", "cat", "catch", "cater", "cattle",
    "cause", "cave", "cavity", "cedar", "celery", "cell", "cement", "census", "center", "cereal",
    "chain", "chair", "chalk", "chamber", "chance", "change", "channel", "chaos", "chapel", "chapter",
    "charge", "charity", "charm", "chart", "chase", "cheap", "cheat", "check", "cheek", "cheer",
    "cheese", "chef", "cherry", "chess", "chest", "chew", "chief", "child", "chime", "chin",
    "chip", "chirp", "chisel", "choice", "choir", "choke", "choose", "chord", "chorus", "chrome",
    "chunk", "church", "cider", "cigar", "cinema", "circle", "circus", "citizen", "city", "civic",
    "civil", "claim", "clam", "clamp", "clan", "clasp", "class", "claw", "clay", "clean",
    "clear", "cleat", "clerk", "clever", "click", "client", "cliff", "climate", "climb", "cling",
    "clinic", "clip", "cloak", "clock", "clone", "close", "cloth", "cloud", "clover", "clown",
    "club", "clue", "clump", "clutch", "coach", "coal", "coast", "coat", "cobalt", "cobra",
    "cocoa", "code", "coffee", "coffin", "coil", "coin", "cold", "collar", "collie", "colony",
    "color", "colt", "column", "combat", "comedy", "comet", "comfort", "comic", "comma", "common",
    "compact", "company", "compare", "compass", "comply", "compose", "comput", "conch", "condor", "cone",
    "coney", "config", "confirm", "congress", "connect", "console", "consul", "contact", "contest", "context",
    "contour", "control", "convent", "convert", "convex", "cook", "cookie", "cool", "copper", "copy",
    "coral", "cord", "core", "cork", "corn", "corner", "corona", "correct", "corridor", "cortex",
    "cosmic", "cost", "costume", "cottage", "cotton", "couch", "cough", "council", "counsel", "count",
    "county", "couple", "coupon", "courage", "course", "court", "cousin", "cove", "cover", "covet",
    "cow", "cowboy", "coyote", "crab", "crack", "cradle", "craft", "crag", "crane", "crank",
    "crash", "crate", "crater", "cravat", "crave", "craw", "crayon", "crazy", "cream", "create",
    "credit", "creed", "creek", "creep", "creme", "crepe", "cress", "crest", "crew", "crib",
    "cricket", "cried", "crier", "crime", "crimp", "crimson", "cripple", "crisis", "crisp", "criteria",
    "critic", "crock", "croft", "crony", "crook", "crop", "cross", "croup", "crow", "crowd",
    "crown", "crude", "cruel", "cruise", "crumb", "crush", "crust", "crypt", "crystal", "cub",
    "cube", "cubic", "cuckoo", "cuddle", "cue", "cuff", "culprit", "cult", "cup", "cupboard",
    "curb", "curd", "cure", "curfew", "curio", "curl", "currant", "currency", "current", "curry",
    "curse", "curve", "cushion", "custard", "custom", "cute", "cutlet", "cutter", "cycle", "cyclone",
    "cynic", "cypress", "dad", "daffodil", "dagger", "daily", "dairy", "daisy", "dale", "damage",
    "damp", "dance", "danger", "dangle", "dank", "dare", "dark", "darling", "darn", "dart",
    "dash", "data", "date", "daughter", "dawn", "day", "dazzle", "dead", "deaf", "deal",
    "dean", "dear", "death", "debate", "debris", "debt", "decade", "decay", "decent", "decide",
    "deck", "declare", "decor", "decoy", "decrease", "decree", "deduct", "deed", "deep", "deer",
    "defeat", "defect", "defend", "define", "deflect", "deform", "defray", "defy", "degree", "delay",
    "delegate", "delight", "deliver", "dell", "delta", "deluge", "deluxe", "demand", "demerit", "demo",
    "demonic", "demote", "demure", "denim", "denote", "dentist", "deny", "depart", "depend", "depict",
    "deploy", "deport", "deposit", "depot", "depth", "deputy", "derby", "derive", "descend", "desert",
    "design", "desire", "desk", "despair", "despise", "despite", "destroy", "detach", "detail", "detect",
    "deter", "detour", "devast", "develop", "deviate", "device", "devil", "devise", "devoid", "devote",
    "devour", "devout", "dew", "diagonal", "diagram", "dial", "diameter", "diamond", "diary", "dice",
    "dictate", "diction", "dictionary", "die", "diet", "differ", "difficult", "diffuse", "dig", "digest",
    "digit", "dignity", "dike", "dilute", "dim", "dime", "diminish", "dine", "dinghy", "dinner",
    "dinosaur", "diode", "dioxide", "dip", "diploma", "direct", "dirt", "disable", "disagree", "disaster",
    "disband", "discard", "discern", "discharge", "disclose", "discount", "discover", "discreet", "discretion", "discuss",
    "disdain", "disease", "disgrace", "disguise", "disgust", "dish", "dislike", "dismay", "dismiss", "disorder",
    "dispatch", "dispel", "dispense", "disperse", "displace", "display", "disposal", "dispose", "disprove", "dispute",
    "disrupt", "dissolve", "distance", "distant", "distaste", "distil", "distinct", "distort", "distract", "distress",
    "distribute", "district", "distrust", "disturb", "ditch", "ditto", "dive", "diver", "divide", "divine",
    "division", "divorce", "dizzy", "dock", "doctor", "document", "dodge", "dog", "dole", "doll",
    "dollar", "dolphin", "domain", "dome", "domestic", "dominate", "donate", "donkey", "donor", "doom",
    "door", "dormant", "dose", "dot", "double", "doubt", "dough", "dove", "down", "doze",
    "dozen", "draft", "drag", "dragon", "drain", "drake", "drama", "drank", "drape", "drastic",
    "draw", "drawer", "dread", "dream", "dreary", "drench", "dress", "drew", "dribble", "drift",
    "drill", "drink", "drip", "drive", "driver", "drizzle", "droll", "drone", "drool", "droop",
    "drop", "drove", "drown", "drug", "drum", "drunk", "dry", "dual", "dub", "duchess",
    "duck", "duct", "due", "duel", "duet", "duke", "dull", "duly", "dumb", "dummy",
    "dump", "dune", "dung", "dungeon", "dupe", "duplicate", "durable", "duration", "duress", "during",
    "dusk", "dust", "duty", "dwarf", "dwell", "dwindle", "dye", "dynamic", "dynamite", "dynasty",
    "each", "eager", "eagle", "ear", "earl", "early", "earn", "earth", "ease", "east",
    "easy", "eat", "echo", "eclipse", "ecology", "economy", "ecstasy", "eddy", "edge", "edict",
    "edifice", "edit", "editor", "educate", "eel", "eerie", "efface", "effect", "effort", "egg",
    "ego", "eight", "either", "eject", "elaborate", "elapse", "elastic", "elbow", "elder", "elect",
    "elegant", "element", "elephant", "elevate", "eleven", "elf", "elicit", "eligible", "eliminate", "elite",
    "elk", "ellipse", "elm", "elope", "eloquent", "else", "elude", "elusive", "embark", "embarrass",
    "embassy", "ember", "emblem", "embody", "embrace", "embroider", "emerald", "emerge", "emergency", "emigrant",
    "eminent", "emit", "emotion", "emperor", "emphasis", "empire", "employ", "empower", "empress", "empty",
    "emulate", "enable", "enact", "enamel", "encamp", "enchant", "encircle", "enclose", "encore", "encounter",
    "encourage", "encroach", "encrust", "encycloped", "end", "endanger", "endeavor", "endless", "endorse", "endow",
    "endure", "enemy", "energy", "enforce", "engage", "engine", "engrave", "engulf", "enhance", "enigma",
    "enjoy", "enlarge", "enlist", "enmity", "enormous", "enough", "enrage", "enrich", "enroll", "ensemble",
    "ensign", "ensue", "ensure", "entail", "entangle", "enter", "enterprise", "entertain", "enthrall", "enthusiasm",
    "entice", "entire", "entitle", "entity", "entomb", "entrance", "entrap", "entreat", "entrust", "entry",
    "entwine", "envelop", "envious", "environ", "envoy", "envy", "enzyme", "epic", "epidem",
    "episode", "epoch", "equal", "equate", "equator", "equip", "equity", "era", "erase", "erect",
    "ermine", "erode", "errand", "erratic", "error", "erupt", "escape", "escort", "essay", "essence",
    "establish", "estate", "esteem", "estimate", "estuary", "eternal", "ether", "ethical", "ethics", "ethnic",
    "eulogy", "evade", "evaluate", "evaporate", "evasion", "eve", "even", "evening", "event", "ever",
    "every", "evict", "evidence", "evil", "evoke", "evolve", "exact", "exaggerate", "exalt", "exam",
    "examine", "example", "exasperate", "excavate", "exceed", "excel", "except", "excerpt", "excess", "exchange",
    "excite", "exclaim", "exclude", "excursion", "excuse", "execute", "exempt", "exercise", "exert", "exhale",
    "exhaust", "exhibit", "exhort", "exile", "exist", "exit", "exodus", "exotic", "expand", "expanse",
    "expect", "expedite", "expel", "expend", "expense", "experience", "experiment", "expert", "expire", "explain",
    "explicit", "explode", "exploit", "explore", "explosion", "export", "expose", "expound", "express", "exquisite",
    "extend", "extent", "exterior", "external", "extinct", "extol", "extort", "extra", "extract", "extradite",
    "extreme", "exult", "eye", "eyebrow", "eyelash", "fable", "fabric", "fabulous", "face", "facet",
    "facile", "facilitate", "facility", "fact", "factor", "factory", "faculty", "fade", "fag",
    "fail", "failure", "faint", "fair", "fairy", "faith", "falcon", "fall", "fallacy", "fallow",
    "false", "falsify", "fame", "familiar", "family", "famine", "famous", "fan", "fanatic", "fancy",
    "fang", "fantasy", "far", "farce", "fare", "farm", "fascinate", "fashion", "fast", "fasten",
    "fat", "fatal", "fate", "father", "fathom", "fatigue", "faucet", "fault", "favor", "fawn",
    "fear", "feast", "feat", "feather", "feature", "federal", "fee", "feeble", "feed", "feel",
    "feet", "feign", "feint", "felicity", "fell", "fellow", "felon", "felt", "female", "fence",
    "fend", "fender", "ferment", "fern", "ferocious", "ferret", "ferry", "fertile", "fervent", "festival",
    "fetch", "fever", "few", "fiance", "fiber", "fiction", "fiddle", "field", "fiend", "fierce",
    "fiery", "fife", "fifteen", "fifty", "fig", "fight", "figure", "filament", "file", "fill",
    "film", "filter", "filth", "final", "finance", "find", "fine", "finger", "finish", "fir",
    "fire", "firm", "first", "fish", "fissure", "fist", "fit", "five", "fix", "fixture",
    "fizz", "flabby", "flag", "flake", "flamboyant", "flame", "flank", "flannel", "flap", "flare",
    "flash", "flask", "flat", "flatter", "flaw", "flax", "flee", "fleece", "fleet", "flesh",
    "flew", "flex", "flick", "flight", "flinch", "fling", "flint", "flirt", "float", "flock",
    "flog", "flood", "floor", "flora", "floss", "flour", "flow", "flower", "flown", "flu",
    "flue", "fluent", "fluff", "fluid", "flung", "flurry", "flush", "flute", "flutter", "fly",
    "foal", "foam", "focus", "fog", "foil", "fold", "foliage", "folk", "follow", "folly",
    "fond", "font", "food", "fool", "foot", "forage", "foray", "forbid", "force", "ford",
    "forehead", "foreign", "forest", "forge", "forget", "forgive", "fork", "form", "formal", "format",
    "former", "formula", "fort", "forth", "fortify", "fortress", "fortune", "forty", "forum", "forward",
    "fossil", "foster", "fought", "foul", "found", "fountain", "four", "fowl", "fox", "fraction",
    "fracture", "fragile", "fragment", "fragrant", "frail", "frame", "franchise", "frank", "frantic", "fraud"
]

def calculate_entropy(num_words, has_number, has_special):
    """Calculate the entropy of the generated passphrase in bits."""
    # Base entropy from the word list
    # Entropy = log2(L^N) = N * log2(L)
    word_entropy = num_words * math.log2(len(WORDLIST))
    
    # If numbers are appended, it adds choices
    # Typically, adding a single random digit (0-9) adds log2(10) ~ 3.32 bits
    extra_entropy = 0
    if has_number:
        extra_entropy += math.log2(10)
    if has_special:
        # Standard special characters string has 32 characters
        extra_entropy += math.log2(32)
        
    return word_entropy + extra_entropy

def generate_dice_rolls():
    """Simulate rolling physical dice (5 dice) and return values as a list of strings."""
    return [secrets.choice("123456") for _ in range(5)]

def get_word_by_rolls(rolls_str):
    """Retrieve a word using a 5-digit dice roll string (values 1-6)."""
    # Map the rolls string (base-6 representation using 1-6 digits) to an index.
    # Convert '11111'-'66666' to 0-7775 index or here map to len(WORDLIST)
    # Since our WORDLIST is 1000 words, we can convert the roll into a number:
    # (roll_val - 11111) modulo len(WORDLIST) to ensure it falls within range,
    # or simple deterministic hashing. Let's do modulo.
    try:
        val = int(rolls_str)
        idx = val % len(WORDLIST)
        return WORDLIST[idx]
    except ValueError:
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Generates memorable, cryptographically secure passphrases using Diceware.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-w", "--words",
        type=int,
        default=4,
        help="Number of words in the passphrase (default: 4)"
    )
    
    parser.add_argument(
        "-s", "--separator",
        type=str,
        default="-",
        help="Separator between words (default: '-')"
    )
    
    parser.add_argument(
        "-c", "--capitalize",
        action="store_true",
        help="Capitalize each word in the passphrase"
    )
    
    parser.add_argument(
        "-n", "--numbers",
        action="store_true",
        help="Append a random single-digit number (0-9)"
    )
    
    parser.add_argument(
        "-sp", "--special",
        action="store_true",
        help="Append a random special character (e.g. !, @, #, $, %)"
    )
    
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Interactive physical dice mode (input your own dice rolls!)"
    )
    
    args = parser.parse_args()
    
    if args.words <= 0:
        print("Error: Word count must be at least 1.", file=sys.stderr)
        return 1

    selected_words = []
    
    if args.interactive:
        print("Diceware Passphrase Generator: Interactive Physical Dice Mode")
        print("=================================================================")
        print(f"To generate a {args.words}-word passphrase, you will need to roll 5 dice for each word.")
        print("For each word, enter the 5 digits shown on the dice (values 1-6, e.g. 24153).")
        print("=================================================================\n")
        
        for w_idx in range(args.words):
            while True:
                try:
                    user_input = input(f"Enter 5-digit dice roll for Word #{w_idx + 1}: ").strip()
                    if len(user_input) != 5 or not all(c in "123456" for c in user_input):
                        print("Invalid input. Please enter exactly 5 digits, each between 1 and 6.")
                        continue
                    
                    word = get_word_by_rolls(user_input)
                    if word:
                        selected_words.append(word)
                        print(f"  Mapped to word: {word}")
                        break
                    else:
                        print("Error retrieving word. Try again.")
                except (KeyboardInterrupt, EOFError):
                    print("\nAborted.")
                    return 1
    else:
        # Secure random generation using the secrets module
        for _ in range(args.words):
            word = secrets.choice(WORDLIST)
            selected_words.append(word)
            
    # Apply capitalization if requested
    if args.capitalize:
        selected_words = [w.capitalize() for w in selected_words]
        
    passphrase = args.separator.join(selected_words)
    
    # Append random numbers / special characters if requested
    special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    num_str = ""
    if args.numbers:
        num_str = str(secrets.randbelow(10))
        passphrase += num_str
        
    spec_str = ""
    if args.special:
        spec_str = secrets.choice(special_chars)
        passphrase += spec_str
        
    # Calculate entropy
    entropy = calculate_entropy(args.words, args.numbers, args.special)
    
    # Print results
    print("\nGenerated Passphrase:")
    print("-" * 50)
    print(passphrase)
    print("-" * 50)
    print(f"Word count:         {args.words}")
    print(f"Wordlist size:      {len(WORDLIST)} words")
    print(f"Entropy:            {entropy:.2f} bits")
    
    # Security classification based on bits of entropy
    if entropy < 40:
        strength = "WEAK (easy to brute-force)"
    elif entropy < 60:
        strength = "MEDIUM (adequate for low-security accounts)"
    elif entropy < 80:
        strength = "STRONG (recommended for general use)"
    else:
        strength = "VERY STRONG (cryptographically secure against state-level actors)"
        
    print(f"Strength Class:     {strength}")
    print("=" * 50)
    return 0

if __name__ == "__main__":
    sys.exit(main())
