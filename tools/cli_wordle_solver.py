#!/usr/bin/env python3
"""
CLI Wordle Game & Solver
A zero-dependency terminal-based Wordle game and solver helper.
Allows playing Wordle in the terminal or solving an external game by inputting feedback.
"""

import argparse
import random
import sys
from collections import Counter

# A built-in list of common 5-letter English words for self-containment
COMMON_WORDS = [
    "about", "above", "actor", "acute", "admit", "adopt", "adult", "after", "again", "agent",
    "agree", "ahead", "alarm", "album", "alert", "alike", "alive", "allow", "alone", "along",
    "alter", "among", "anger", "angle", "angry", "apart", "apple", "apply", "arena", "argue",
    "arise", "array", "arrow", "aside", "asset", "audio", "audit", "avoid", "award", "aware",
    "badly", "baker", "bases", "basic", "basis", "beach", "beard", "beast", "begin", "being",
    "below", "bench", "bible", "birth", "black", "blade", "blame", "blind", "block", "blood",
    "board", "boost", "booth", "bound", "brain", "brand", "bread", "break", "breed", "brick",
    "bride", "brief", "bring", "broad", "broke", "brown", "brush", "buyer", "cabin", "cable",
    "calmly", "camel", "camera", "camp", "canal", "candy", "canon", "cargo", "carol", "carry",
    "carve", "cases", "catch", "cater", "cause", "cedar", "chain", "chair", "chalk", "champ",
    "chant", "chaos", "charm", "chart", "chase", "cheap", "cheat", "check", "cheek", "cheer",
    "chess", "chest", "chief", "child", "chime", "china", "chips", "choir", "choke", "chord",
    "chore", "chose", "chuck", "cider", "cigar", "claim", "clamp", "clans", "clash", "clasp",
    "class", "claws", "clay", "clean", "clear", "cleft", "clerk", "click", "cliff", "climb",
    "cling", "clip", "cloak", "clock", "close", "cloth", "cloud", "clove", "clown", "clubs",
    "cluck", "clump", "clung", "coach", "coast", "cobra", "cocoa", "coded", "coder", "codes",
    "coils", "coins", "colds", "colic", "colon", "colts", "combs", "comer", "comes", "comet",
    "comfy", "comic", "comma", "conch", "condo", "coned", "cones", "coney", "conga", "conic",
    "cooks", "cools", "copse", "coral", "cords", "cored", "cores", "corgi", "corky", "corns",
    "corny", "corps", "costs", "couch", "cough", "could", "count", "coupe", "court", "cover",
    "covet", "covey", "cowed", "cower", "cowls", "cowry", "coxes", "coyly", "cozen", "cozey",
    "cozie", "crabs", "crack", "craft", "crags", "cramp", "crams", "crane", "crank", "crape",
    "craps", "crash", "crass", "crate", "crave", "craws", "craze", "crazy", "creak", "cream",
    "credo", "creed", "creek", "creel", "creep", "crepe", "crept", "cress", "crest", "crews",
    "cribs", "cried", "crier", "cries", "crime", "crimp", "crisp", "croak", "crock", "crocs",
    "croft", "crone", "crony", "crook", "croon", "crops", "cross", "croup", "crowd", "crown",
    "crows", "crude", "cruel", "cruet", "crumb", "crump", "cruse", "crust", "crypt", "cubes",
    "cubic", "cubit", "cuffs", "culls", "culms", "cults", "cumin", "cupid", "cuppa", "curbs",
    "curds", "curdy", "cured", "curer", "cures", "curia", "curio", "curls", "curly", "curry",
    "curse", "curve", "curvy", "cushy", "cusps", "cuter", "cutie", "cutis", "cutts", "cycad",
    "cycle", "cyclo", "cynic", "cysts", "czars", "daily", "dairy", "daisy", "dance", "dandy",
    "death", "delay", "depth", "dirty", "doing", "doubt", "dozen", "draft", "drama", "dream",
    "dress", "drink", "drive", "drove", "dying", "eager", "early", "earth", "eight", "elite",
    "empty", "enemy", "enjoy", "enter", "entry", "equal", "error", "event", "every", "exact",
    "exist", "extra", "faith", "false", "fancy", "fatal", "favor", "feast", "fiber", "field",
    "fifth", "fifty", "fight", "final", "first", "five", "flame", "flash", "flat", "fleet",
    "flesh", "float", "flood", "floor", "fluid", "flyer", "focus", "force", "forest", "forge",
    "formal", "forte", "forth", "forty", "forum", "found", "frame", "frank", "fraud", "fresh",
    "front", "fruit", "fully", "funny", "giant", "given", "glass", "globe", "glory", "glove",
    "grace", "grade", "grain", "grand", "grant", "grave", "great", "green", "grief", "gross",
    "group", "grown", "guard", "guess", "guest", "guide", "habit", "happy", "harsh", "haven",
    "heart", "heavy", "hence", "honey", "honor", "horse", "hotel", "house", "human", "humor",
    "hurry", "ideal", "image", "imply", "index", "inner", "input", "irony", "issue", "ivory",
    "joint", "judge", "juice", "knife", "knock", "known", "label", "labor", "large", "laser",
    "later", "laugh", "layer", "learn", "lease", "least", "leave", "legal", "lemon", "level",
    "lever", "light", "limit", "lunch", "lying", "magic", "major", "maker", "march", "match",
    "maybe", "mayor", "meant", "media", "metal", "might", "minor", "minus", "mixed", "model",
    "money", "month", "moral", "motor", "mount", "mouse", "mouth", "movie", "music", "needs",
    "never", "newly", "night", "ninth", "noise", "north", "noted", "novel", "nurse", "occur",
    "ocean", "offer", "often", "order", "other", "ought", "ounce", "outer", "owned", "owner",
    "paint", "panel", "paper", "party", "patch", "path", "patio", "peace", "peach", "pearl",
    "pedal", "phase", "phone", "photo", "piano", "pick", "piece", "pilot", "pitch", "pizza",
    "place", "plain", "plane", "plant", "plate", "plays", "plaza", "plead", "plent", "point",
    "poker", "polar", "poles", "police", "polio", "polka", "polls", "polyp", "ponds", "pones",
    "pooch", "poofs", "poofy", "poohs", "pools", "poops", "popes", "poppa", "poppy", "porch",
    "pored", "pores", "porgy", "porks", "porky", "porns", "ports", "posed", "poser", "poses",
    "posey", "posse", "posts", "potch", "potty", "pouch", "poult", "pound", "pours", "pouts",
    "power", "poxes", "prams", "prang", "prank", "prate", "prats", "prawn", "prays", "preen",
    "preps", "press", "prexy", "preys", "price", "prick", "pricy", "pride", "pried", "prier",
    "pries", "prill", "prima", "prime", "primo", "primp", "prims", "prink", "print", "prior",
    "prise", "prism", "priss", "privy", "prize", "proas", "probe", "probs", "prods", "proem",
    "profs", "progs", "prole", "promo", "proms", "prone", "prong", "proof", "props", "prose",
    "proso", "pross", "prost", "prosy", "proud", "prove", "prowl", "prows", "proxy", "prude",
    "prune", "prunt", "pruta", "pryer", "prying", "psalm", "pseud", "pshaw", "psoas", "psych",
    "pubes", "pubic", "pubis", "public", "puces", "pucks", "pudgy", "pudus", "puffs", "puffy",
    "puggy", "pujah", "pujas", "puked", "pukes", "pukey", "pulas", "puled", "puler", "pules",
    "pulik", "pulis", "pulks", "pulls", "pulps", "pulpy", "pulse", "pumas", "pumps", "punas",
    "punch", "pungs", "punji", "punka", "punks", "punky", "punny", "punto", "punts", "punty",
    "pupae", "pupal", "pupas", "pupil", "puppy", "pupus", "purda", "puree", "purer", "purge",
    "purin", "puris", "purls", "purps", "purrs", "purse", "pursy", "purty", "puses", "pushy",
    "pussy", "puton", "putti", "putto", "putts", "putty", "pygmy", "pyins", "pylon", "pyoid",
    "pyran", "pyres", "pyrex", "pyric", "pyros", "queen", "query", "quest", "queue", "quick",
    "quiet", "quilt", "quite", "quote", "radar", "radio", "raise", "range", "rapid", "ratio",
    "reach", "ready", "refer", "reign", "relax", "reply", "reset", "reuse", "rider", "ridge",
    "right", "rival", "river", "robot", "rocks", "rocky", "rogue", "roles", "roman", "rough",
    "round", "route", "royal", "rugby", "ruler", "rural", "sadly", "safer", "saint", "salad",
    "sales", "salon", "sandy", "satin", "sauce", "saved", "scale", "scare", "scene", "scent",
    "scope", "score", "scout", "scrap", "scream", "screen", "screw", "script", "scrub", "scuba",
    "seals", "seamy", "seats", "seedy", "seize", "sells", "semen", "sends", "sense", "serum",
    "seven", "sever", "sewer", "shack", "shade", "shadow", "shady", "shaft", "shake", "shaky",
    "shall", "shame", "shampoo", "shape", "share", "shark", "sharp", "shave", "shear", "sheds",
    "sheen", "sheep", "sheer", "sheet", "shelf", "shell", "shift", "shine", "shiny", "ships",
    "shirt", "shock", "shoes", "shook", "shoot", "shops", "shore", "short", "shots", "shout",
    "shove", "shown", "shows", "shrub", "shrug", "shuns", "shunt", "shush", "shuts", "shyly",
    "sight", "sigma", "signs", "silent", "silly", "silver", "since", "singe", "single", "sinks",
    "siren", "sites", "sixes", "sixth", "sixty", "sizes", "skate", "sketch", "skews", "skids",
    "skied", "skier", "skies", "skiff", "skill", "skimp", "skims", "skins", "skint", "skips",
    "skirt", "skits", "skuaq", "skuds", "skulk", "skull", "skunk", "skyed", "skyey", "slabs",
    "slack", "slags", "slain", "slake", "slams", "slang", "slank", "slant", "slaps", "slash",
    "slate", "slats", "slaty", "slave", "slaws", "slays", "sleek", "sleep", "sleet", "slept",
    "slice", "slick", "slide", "slier", "slily", "slime", "slimy", "sling", "slink", "slips",
    "slipt", "slits", "sliver", "slobs", "sloes", "slogs", "sloid", "sloop", "slope", "slops",
    "slosh", "sloth", "slots", "slows", "slubs", "slued", "slues", "sluff", "slugs", "slump",
    "slums", "slung", "slunk", "slurp", "slurs", "slush", "sluts", "slyly", "smack", "small",
    "smalt", "smart", "smash", "smear", "smell", "smelt", "smile", "smirk", "smite", "smith",
    "smock", "smoke", "smoky", "smolt", "smote", "smuts", "snack", "snafu", "snags", "snail",
    "snake", "snaky", "snaps", "snare", "snark", "snarl", "snash", "snath", "snaws", "sneak",
    "sneap", "sneck", "sneer", "snell", "snibs", "snick", "snide", "snies", "sniff", "snift",
    "snigs", "snipe", "snips", "snipy", "snits", "snobs", "snods", "snook", "snool", "snoop",
    "snoot", "snows", "snowy", "snubs", "snuds", "snuff", "snugs", "snyes", "soaks", "soaps",
    "soapy", "soars", "soave", "sober", "socks", "socle", "sodas", "sodic", "sofas", "softa",
    "softs", "softy", "soger", "soils", "soily", "sojus", "sokah", "soken", "solan", "solar",
    "solas", "solde", "soldi", "soldo", "solds", "soled", "soles", "solid", "solon", "solos",
    "solum", "solus", "solve", "soman", "somas", "sonar", "sonde", "sones", "songs", "sonic",
    "sonly", "sonse", "sonsy", "soobs", "soods", "soofs", "sooky", "sools", "sooms", "soops",
    "sooth", "soots", "sooty", "sophs", "sophy", "sopor", "soppy", "sopra", "soras", "sorbs",
    "sorda", "sordo", "sords", "sored", "soree", "sorel", "sores", "sorex", "sorgo", "sorgs",
    "sorra", "sorry", "sorta", "sorts", "sorus", "sotol", "souce", "souct", "sough", "souks",
    "souls", "soums", "sound", "soups", "soupy", "sourc", "sourd", "soure", "sours", "souse",
    "south", "souts", "sowar", "sowce", "sowed", "sower", "sowle", "sowls", "sowms", "sownd",
    "sowne", "sowps", "sowse", "sowth", "soyas", "soyuz", "sozen", "space", "spade", "spado",
    "spaed", "spaes", "spags", "spahi", "spail", "spain", "spait", "spake", "spald", "spale",
    "spall", "spamp", "spams", "spand", "spang", "spank", "spans", "sparc", "spare", "spark",
    "spars", "spart", "spasm", "spate", "spats", "spaul", "spave", "spawl", "spawn", "spaws",
    "spayd", "spays", "speak", "speal", "spean", "spear", "speat", "speck", "specs", "spect",
    "speed", "speel", "speer", "speil", "speir", "speks", "speld", "spelk", "spell", "spelt",
    "spend", "spent", "speos", "sperm", "spews", "spewy", "spial", "spica", "spice", "spick",
    "spics", "spicy", "spide", "spied", "spiel", "spier", "spies", "spiff", "spifs", "spigg",
    "spika", "spike", "spiky", "spile", "spill", "spilt", "spime", "spina", "spine", "spink",
    "spins", "spiny", "spire", "spirt", "spiry", "spite", "spits", "spitz", "spivs", "splay",
    "split", "spode", "spods", "spoil", "spoke", "spoof", "spook", "spool", "spoon", "spoor",
    "spoot", "spore", "sport", "sposh", "spots", "spout", "sprad", "sprag", "sprat", "spray",
    "spred", "spree", "spret", "sprew", "sprig", "sprim", "sprit", "sprod", "sprog", "spros",
    "sprow", "sprug", "sprun", "spuds", "spudy", "spued", "spuer", "spues", "spugs", "spule",
    "spume", "spumy", "spung", "spunk", "spurn", "spurs", "spurt", "sputa", "spyal", "spyre",
    "squab", "squad", "squat", "squaw", "squeg", "squib", "squid", "squim", "squit", "squiz",
    "stabs", "stack", "stade", "staff", "stage", "stags", "stagy", "staid", "staig", "stain",
    "stair", "stake", "stale", "stalk", "stall", "stamp", "stand", "stane", "stang", "stank",
    "stans", "stape", "staps", "stare", "stark", "starn", "starr", "stars", "start", "stash",
    "state", "stats", "staun", "stave", "staws", "stays", "stead", "steak", "steal", "steam",
    "stean", "stech", "stedd", "stede", "steds", "steed", "steek", "steel", "steem", "steep",
    "steer", "steid", "stein", "stela", "stele", "stell", "steme", "stems", "stend", "stent",
    "steps", "stept", "stere", "steri", "sterk", "stern", "stero", "sterp", "stert", "steve",
    "stewy", "stews", "steyx", "stial", "stibo", "stich", "stick", "stied", "stier", "sties",
    "stiff", "stilb", "stile", "still", "stilt", "stime", "stims", "stimy", "sting", "stink",
    "stint", "stipa", "stipe", "stire", "stirk", "stirp", "stirs", "stive", "stivy", "stoae",
    "stoai", "stoas", "stoat", "stobs", "stock", "stodt", "stoep", "stoft", "stogs", "stoic",
    "stoke", "stola", "stole", "stolt", "stoma", "stomp", "stond", "stone", "stong", "stonk",
    "stony", "stood", "stoof", "stook", "stool", "stoop", "stoor", "stoot", "stope", "stops",
    "stopt", "store", "stork", "storm", "story", "stotz", "stoun", "stoup", "stour", "stous",
    "stout", "stove", "stowp", "stows", "stoyn", "strap", "straw", "stray", "strep", "strew",
    "stria", "strip", "strog", "strow", "stroy", "strub", "strum", "strut", "struv", "stubs",
    "stuck", "stude", "studs", "study", "stuff", "stull", "stulp", "stume", "stump", "stums",
    "stung", "stunk", "stuns", "stunt", "stupa", "stupe", "sture", "sturt", "stutz", "style",
    "styli", "stylo", "styme", "stymy", "styre", "styte", "suave", "sugar", "suite", "suits",
    "sunny", "super", "sweet", "swept", "swift", "swing", "swiss", "sword", "syrup", "table",
    "taken", "taste", "tasty", "teach", "teeth", "tempo", "tenor", "thank", "their", "theme",
    "there", "these", "thick", "thief", "thigh", "thing", "think", "third", "those", "three",
    "threw", "throw", "tiger", "tight", "times", "tired", "title", "today", "token", "topic",
    "total", "touch", "tough", "tower", "toxic", "trace", "track", "trade", "trail", "train",
    "trait", "treat", "trend", "trial", "tribe", "trick", "tried", "tries", "trio", "troop",
    "trout", "crowd", "truck", "truly", "trunk", "trust", "truth", "twice", "under", "union",
    "unite", "unity", "until", "upper", "upset", "urban", "usage", "using", "usual", "vague",
    "valid", "value", "vapor", "vault", "venus", "video", "vinyl", "viral", "virus", "visit",
    "vital", "voice", "wagon", "waist", "waste", "watch", "water", "wheel", "where", "which",
    "while", "white", "whole", "whose", "woman", "women", "world", "worry", "worse", "worst",
    "worth", "would", "wound", "write", "wrong", "wrote", "yield", "young", "youth", "zebra"
]

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_GRAY = "\033[90m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def colorize(text, color):
    return f"{color}{text}{COLOR_RESET}"


def evaluate_guess(guess, target):
    """
    Evaluates a guess against the target word.
    Returns a list of characters representing colors: 'G' for Green, 'Y' for Yellow, 'X' for Gray.
    Handles duplicate letters properly (standard Wordle rules).
    """
    feedback = ['X'] * 5
    target_counts = Counter(target)
    
    # First pass: find exact matches (Green)
    for i in range(5):
        if guess[i] == target[i]:
            feedback[i] = 'G'
            target_counts[guess[i]] -= 1
            
    # Second pass: find partial matches (Yellow)
    for i in range(5):
        if feedback[i] != 'G' and guess[i] in target_counts and target_counts[guess[i]] > 0:
            feedback[i] = 'Y'
            target_counts[guess[i]] -= 1
            
    return "".join(feedback)


def format_feedback_cli(guess, feedback):
    """Formats the guess string with terminal colors based on feedback."""
    formatted = []
    for char, color_code in zip(guess, feedback):
        if color_code == 'G':
            formatted.append(colorize(char.upper(), COLOR_GREEN))
        elif color_code == 'Y':
            formatted.append(colorize(char.upper(), COLOR_YELLOW))
        else:
            formatted.append(colorize(char.upper(), COLOR_GRAY))
    return " ".join(formatted)


def play_game(target_word=None):
    """Launches the interactive Wordle game."""
    if not target_word:
        target_word = random.choice(COMMON_WORDS)
    
    print("\n" + "=" * 40)
    print(colorize("           CLI WORDLE GAME", COLOR_BOLD + COLOR_GREEN))
    print("=" * 40)
    print("Guess the 5-letter word in 6 tries.")
    print(f"Colors: {colorize('GREEN', COLOR_GREEN)} (Correct spot), "
          f"{colorize('YELLOW', COLOR_YELLOW)} (Wrong spot), "
          f"{colorize('GRAY', COLOR_GRAY)} (Not in word)\n")

    history = []
    
    for attempt in range(1, 7):
        while True:
            try:
                guess = input(f"Attempt {attempt}/6: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print("\nGoodbye!")
                sys.exit(0)
                
            if len(guess) != 5:
                print("Error: Word must be exactly 5 letters long.")
                continue
            if not guess.isalpha():
                print("Error: Word must contain letters only.")
                continue
            break
            
        feedback = evaluate_guess(guess, target_word)
        history.append((guess, feedback))
        
        # Display current board status
        print("\n--- Board ---")
        for g, f in history:
            print("  " + format_feedback_cli(g, f))
        print("-------------\n")
        
        if guess == target_word:
            print(colorize(f"Congratulations! You won in {attempt} attempts!", COLOR_BOLD + COLOR_GREEN))
            return
            
    print(colorize(f"Game Over! The target word was: {target_word.upper()}", COLOR_BOLD + COLOR_YELLOW))


class WordleSolver:
    def __init__(self, words_list):
        self.all_words = words_list
        self.possible_words = list(words_list)
        self.attempts = []

    def add_feedback(self, guess, feedback):
        """
        Filters the word list based on the feedback.
        Feedback format is a string of 5 characters from {'G', 'Y', 'X'}:
        e.g. 'GXXYX' -> Green, Gray, Gray, Yellow, Gray
        """
        guess = guess.lower()
        feedback = feedback.upper()
        self.attempts.append((guess, feedback))
        
        new_possible = []
        for word in self.possible_words:
            # Check if this word generates the exact same feedback for the guess
            if evaluate_guess(guess, word) == feedback:
                new_possible.append(word)
        self.possible_words = new_possible

    def get_suggestions(self, limit=10):
        """
        Suggests words based on letter frequency in the remaining word list.
        """
        if not self.possible_words:
            return []
            
        # Count letter frequency at each position in remaining possible words
        pos_freq = [Counter() for _ in range(5)]
        overall_freq = Counter()
        for word in self.possible_words:
            for i, char in enumerate(word):
                pos_freq[i][char] += 1
                overall_freq[char] += 1
                
        # Score each word in the list based on letter frequencies
        # Higher score goes to words with more common letters (encouraging elimination)
        scored_words = []
        for word in self.possible_words:
            score = 0
            seen_chars = set()
            for i, char in enumerate(word):
                # Reward letter appearing at this specific position
                score += pos_freq[i][char]
                # Reward general frequency if letter is unique in this word
                if char not in seen_chars:
                    score += overall_freq[char] * 1.5
                    seen_chars.add(char)
            scored_words.append((word, score))
            
        scored_words.sort(key=lambda x: x[1], reverse=True)
        return scored_words[:limit]


def run_solver():
    """Launches the Wordle solver helper."""
    solver = WordleSolver(COMMON_WORDS)
    print("\n" + "=" * 40)
    print(colorize("          CLI WORDLE SOLVER", COLOR_BOLD + COLOR_YELLOW))
    print("=" * 40)
    print("Input your guesses and feedback to find the best next moves.")
    print("Feedback letters: G = Green, Y = Yellow, X = Gray (e.g., GXXYX)\n")

    while True:
        suggestions = solver.get_suggestions()
        print(f"Remaining possible words: {len(solver.possible_words)}")
        if not solver.possible_words:
            print(colorize("No matching words found in database! Try checking your feedback inputs.", COLOR_BOLD + COLOR_YELLOW))
            break
            
        print("Recommended Guesses:")
        for word, score in suggestions[:5]:
            print(f"  - {word.upper()} (score: {int(score)})")
        print()
        
        try:
            guess = input("Enter your guess (or 'q' to quit): ").strip().lower()
            if guess == 'q':
                break
            if len(guess) != 5 or not guess.isalpha():
                print("Error: Guess must be 5 alphabetical letters.")
                continue
                
            feedback = input("Enter feedback received (5 letters of G/Y/X): ").strip().upper()
            if len(feedback) != 5 or not all(c in 'GYX' for c in feedback):
                print("Error: Feedback must be exactly 5 characters of G, Y, or X.")
                continue
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
            
        solver.add_feedback(guess, feedback)
        print("-" * 40)


def main():
    parser = argparse.ArgumentParser(description="CLI Wordle Game & Solver")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--play", action="store_true", help="Play interactive Wordle game")
    group.add_argument("--solve", action="store_true", help="Run interactive solver helper")
    group.add_argument("--word", type=str, help="Play with a custom secret word (for testing)")
    
    args = parser.parse_args()
    
    # If no arguments provided, ask interactive preference
    if not (args.play or args.solve or args.word):
        print("Welcome to CLI Wordle!")
        print("1. Play Wordle Game")
        print("2. Solve an External Wordle")
        try:
            choice = input("Choose option (1/2): ").strip()
            if choice == "1":
                play_game()
            elif choice == "2":
                run_solver()
            else:
                print("Invalid choice. Exiting.")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
    elif args.word:
        word = args.word.strip().lower()
        if len(word) != 5 or not word.isalpha():
            print("Error: Custom secret word must be 5 alphabetical letters.")
            sys.exit(1)
        play_game(word)
    elif args.play:
        play_game()
    elif args.solve:
        run_solver()


if __name__ == "__main__":
    main()
