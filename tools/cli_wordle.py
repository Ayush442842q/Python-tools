#!/usr/bin/env python3
"""
CLI Wordle

An interactive terminal-based Wordle game written in pure Python. Features
ansi colored board feedback (Green for correct, Yellow for present, Gray for
absent), a live keyboard letter status indicator, game statistics (win/loss
ratio, guess distribution, streaks), support for practice sessions, and custom
secret words.

Usage:
    python tools/cli_wordle.py [options]

Options:
    -w, --word WORD       Specify a custom 5-letter secret word for a friend to guess
    -s, --stats           View historical gameplay statistics and exit
    -h, --help            Show this help message and exit
"""

import argparse
import json
import os
import random
import sys
from typing import Dict, List, Set, Tuple, Optional

# ANSI Colors
CLR_GREEN = "\033[42m\033[30m"   # green bg, black text
CLR_YELLOW = "\033[43m\033[30m"  # yellow bg, black text
CLR_GRAY = "\033[100m\033[37m"   # grey bg, white text
CLR_RESET = "\033[0m"

CLR_FG_GREEN = "\033[92m"
CLR_FG_YELLOW = "\033[93m"
CLR_FG_GRAY = "\033[90m"
CLR_CYAN = "\033[96m"
CLR_BOLD = "\033[1m"

STATS_FILE = os.path.expanduser("~/.cli_wordle_stats.json")

# A curated list of common 5-letter English words for target and validation
WORD_BANK = [
    "about", "above", "actor", "acute", "admit", "adopt", "adult", "after", "again", "agent",
    "agree", "ahead", "alarm", "album", "alert", "alike", "alive", "allow", "alone", "along",
    "alter", "among", "anger", "angle", "angry", "apart", "apple", "apply", "arena", "argue",
    "arise", "array", "arrow", "aside", "asset", "audio", "audit", "avoid", "award", "aware",
    "badly", "baker", "bases", "basic", "basis", "beach", "beard", "beast", "begin", "being",
    "below", "bench", "bible", "birth", "black", "blade", "blame", "blind", "block", "blood",
    "board", "boast", "bonus", "boost", "bound", "brain", "brand", "bread", "break", "breed",
    "brick", "bride", "brief", "bring", "broad", "broke", "brown", "brush", "build", "built",
    "buyer", "cable", "calmly", "camel", "camera", "camp", "canal", "candy", "canon", "cargo",
    "carol", "carry", "carve", "case", "catch", "cater", "cause", "cedar", "chain", "chair",
    "chalk", "champ", "chant", "chaos", "charm", "chart", "chase", "cheap", "cheat", "check",
    "cheek", "cheer", "chess", "chest", "chief", "child", "chime", "china", "chips", "choir",
    "choke", "chord", "chore", "chose", "chuck", "chunk", "churn", "cider", "cigar", "claim",
    "clamp", "clans", "clash", "clasp", "class", "clean", "clear", "cleft", "clerk", "click",
    "cliff", "climb", "cling", "cloak", "clock", "clone", "close", "cloth", "cloud", "clove",
    "clown", "clump", "clung", "coach", "coast", "cobra", "cocoa", "codes", "coils", "coins",
    "colts", "comet", "comfy", "comic", "comma", "conch", "cones", "coney", "coped", "copes",
    "coral", "cords", "cored", "cores", "corgi", "corky", "corns", "corny", "corps", "costs",
    "couch", "cough", "could", "count", "coupe", "court", "cover", "covet", "covey", "cowed",
    "cower", "cowry", "coxed", "coxes", "coyly", "cozen", "cozey", "cozily", "cozy", "crabs",
    "crack", "craft", "crags", "cramp", "crams", "crane", "crank", "crape", "craps", "crash",
    "crass", "crate", "crave", "crawl", "craws", "craze", "crazy", "creak", "cream", "credo",
    "creed", "creek", "creel", "creep", "crepe", "crept", "cress", "crest", "crews", "cribs",
    "crick", "cried", "crier", "cries", "crime", "crimp", "crisp", "croak", "crock", "crocs",
    "croft", "crone", "crony", "crook", "croon", "crops", "cross", "croup", "crowd", "crown",
    "crows", "crude", "cruel", "cruet", "crumb", "crump", "cruse", "crush", "crust", "crusty",
    "crypt", "cubes", "cubic", "cubit", "cudgel", "cuffs", "cuing", "culls", "cults", "cumin",
    "cunts", "cupid", "curbs", "curds", "curdy", "cured", "curer", "cures", "curio", "curls",
    "curly", "curry", "curse", "curst", "curve", "curvy", "cusec", "cushy", "cusps", "cuspy",
    "cuter", "cutes", "cutey", "cutie", "cutis", "cutup", "cycad", "cycle", "cyclo", "cynic",
    "cysts", "czars", "daily", "dairy", "daisy", "dance", "dandy", "death", "delay", "depth",
    "dirty", "disks", "doing", "donor", "doubt", "dough", "dozen", "draft", "drama", "drawl",
    "drawn", "dread", "dream", "dress", "dried", "drift", "drill", "drink", "drive", "drove",
    "drown", "drugs", "drunk", "dryer", "dryly", "dummy", "dumpy", "dusty", "dwarf", "dwell",
    "dwelt", "dying", "eager", "eagle", "early", "earth", "easel", "eight", "elbow", "elder",
    "elect", "elite", "empty", "enact", "enemy", "enjoy", "enter", "entry", "equal", "equip",
    "erase", "error", "erupt", "essay", "ether", "ethics", "evade", "event", "every", "evict",
    "exact", "excel", "exert", "exile", "exist", "extra", "faint", "fairy", "faith", "false",
    "fancy", "fatal", "fault", "favor", "feast", "fetch", "fiber", "field", "fifth", "fifty",
    "fight", "filet", "final", "finch", "finds", "first", "fishy", "five", "fixer", "flack",
    "flags", "flail", "flair", "flake", "flaky", "flame", "flank", "flans", "flaps", "flare",
    "flash", "flask", "flats", "flaws", "flawy", "flays", "fleas", "fleck", "flees", "fleet",
    "flesh", "fleshy", "flick", "flier", "flies", "fling", "flint", "flips", "flirt", "flits",
    "float", "flock", "flogs", "flood", "floor", "flops", "flora", "flour", "flout", "flown",
    "flows", "flubs", "flues", "fluff", "fluid", "fluke", "fluky", "flume", "flump", "flung",
    "flush", "flute", "fluty", "flyer", "flyby", "foals", "foams", "foamy", "focal", "focus",
    "fogey", "foggy", "foils", "foist", "folds", "folic", "folio", "folks", "folly", "fonts",
    "foods", "fools", "foots", "footy", "foray", "force", "fords", "fores", "forge", "forgo",
    "forks", "forky", "forms", "forte", "forth", "forts", "forty", "forum", "fossa", "fosse",
    "fouls", "found", "fount", "fours", "fovea", "fowls", "foxed", "foxes", "foyer", "frags",
    "frail", "frame", "franc", "frank", "fraps", "frass", "frats", "fraud", "frays", "freak",
    "freed", "freer", "frees", "fresh", "frets", "friar", "fried", "frier", "fries", "frill",
    "frise", "frisk", "frith", "frits", "frock", "frogs", "frond", "frons", "front", "frore",
    "frosh", "frost", "froth", "frown", "frows", "frozen", "frugal", "fruit", "frump", "fryer",
    "fudge", "fuels", "fugal", "fugue", "fuggy", "fulls", "fully", "fumed", "fumer", "fumes",
    "funds", "fungi", "fungo", "funks", "funky", "funny", "furls", "furry", "furze", "furzy",
    "fused", "fusee", "fuses", "fusil", "fussy", "fusty", "futon", "fuzzy", "gabby", "gable",
    "gaddi", "gadget", "gaffe", "gaily", "gains", "gaits", "galah", "galas", "galaxy", "gales",
    "galls", "gally", "galop", "gamer", "games", "gamey", "gamic", "gamin", "gamma", "gamut",
    "heads", "heavy", "hello", "hence", "hotel", "house", "human", "ideal", "image", "imply",
    "index", "inner", "input", "irony", "issue", "items", "ivory", "jeans", "joint", "judge",
    "juice", "juicy", "kings", "kneel", "knees", "knife", "knock", "knots", "known", "knows",
    "label", "labor", "lakes", "lamps", "large", "laser", "later", "laugh", "layer", "leads",
    "leafy", "learn", "lease", "least", "leave", "legal", "lemon", "level", "lever", "light",
    "liked", "likes", "limbo", "limit", "lined", "linen", "lines", "links", "lions", "lipid",
    "liquid", "lists", "lived", "lively", "lives", "local", "locks", "lodge", "logic", "logon",
    "logos", "loose", "lordy", "loser", "loses", "lossy", "lotus", "loved", "lovely", "lover",
    "loves", "lower", "loyal", "lucky", "lunar", "lunch", "lungs", "lying", "macaw", "macro",
    "madam", "mafia", "magic", "magma", "maims", "maing", "mains", "major", "maker", "makes",
    "males", "malts", "malty", "mamas", "mamba", "mambo", "mamma", "mammy", "manas", "maned",
    "manes", "manga", "mange", "mango", "mangy", "mania", "manic", "manly", "manna", "manor",
    "manse", "manta", "maple", "march", "mares", "maria", "marks", "marls", "marly", "marry",
    "marsh", "marts", "maser", "mashy", "masks", "mason", "masse", "massy", "masts", "match",
    "mated", "mater", "mates", "matey", "maths", "matin", "matte", "matts", "matza", "mauls",
    "mauve", "mavis", "maxes", "maxim", "maxis", "mayas", "maybe", "mayos", "mayor", "peace",
    "peach", "peaks", "peaky", "peals", "pearl", "pears", "peart", "pease", "peats", "peaty",
    "peavy", "pecan", "pecks", "pedal", "peds", "peeks", "peels", "peens", "peeps", "peers",
    "peery", "peeve", "peggy", "peins", "peise", "pekan", "pekes", "pekin", "pekoe", "pelts",
    "penal", "pence", "pends", "pengo", "penis", "penny", "peons", "peony", "pepla", "pepos",
    "perch", "perdu", "perdy", "peril", "peris", "perks", "perky", "perms", "pesky", "pesos",
    "pesto", "pests", "pesty", "petal", "peter", "petit", "petti", "petto", "petty", "pewee",
    "pewit", "phage", "phase", "phial", "phlox", "phone", "phono", "phons", "phony", "photo",
    "phots", "phpht", "phyla", "phyle", "piano", "pians", "pibal", "pical", "picas", "picks",
    "picky", "picot", "picra", "picul", "piece", "piend", "piers", "piert", "pieta", "piets",
    "piety", "piezo", "piggy", "pight", "pigmy", "piing", "pikas", "piked", "piker", "pikes",
    "pikey", "pilar", "pilau", "pilaw", "pilea", "piled", "pilei", "piles", "pilis", "pills",
    "pilot", "pilus", "pimas", "pimps", "pinas", "pinch", "pined", "pines", "piney", "pingo",
    "pings", "pinko", "pinks", "pinky", "pinna", "pinny", "pinon", "pinot", "pinta", "pinto",
    "pints", "pinup", "pions", "piony", "pious", "ready", "route", "royal", "rules", "rural",
    "scale", "scare", "scene", "scent", "scope", "score", "seven", "shade", "shaft", "shake",
    "share", "sharp", "shave", "shear", "sheep", "sheet", "shelf", "shell", "shift", "shine",
    "shiny", "ships", "shirt", "shock", "shoes", "shone", "shook", "shoot", "shore", "short",
    "shout", "shove", "shown", "shows", "shrub", "shrug", "sides", "sight", "sigma", "signs",
    "silly", "since", "sites", "sixes", "sixth", "sixty", "sized", "sizes", "skate", "skill",
    "skins", "skirt", "skull", "skyed", "slate", "slave", "sleek", "sleep", "sleet", "slept",
    "slice", "slide", "slips", "slope", "slots", "slows", "slung", "small", "smart", "smash",
    "smell", "smile", "smoke", "smoky", "snack", "snail", "snake", "sneak", "snows", "snowy",
    "sober", "socks", "solar", "solid", "solve", "songs", "sonic", "sorry", "sorts", "souls",
    "sound", "south", "space", "spade", "speak", "speed", "spell", "spend", "spent", "spies",
    "spine", "spiny", "spire", "spite", "split", "spoke", "sport", "spots", "spray", "spree",
    "spring", "squad", "squat", "stage", "stain", "stair", "stake", "stale", "stall", "stamp",
    "stand", "stare", "stark", "stars", "start", "state", "stats", "stave", "stays", "stead",
    "steak", "steal", "steam", "steel", "steep", "steer", "stem", "steps", "slide", "stone",
    "stood", "stool", "stoop", "stops", "store", "storm", "story", "strap", "straw", "stray",
    "strip", "strut", "stuck", "study", "stuff", "stump", "stung", "style", "sugar", "suite",
    "suits", "sunny", "super", "surge", "sushi", "swear", "sweat", "sweep", "sweet", "swept",
    "swift", "swims", "swine", "swing", "swipe", "swirl", "sword", "swore", "sworn", "swung",
    "table", "taken", "takes", "tales", "talks", "talon", "tamed", "tamer", "tames", "tangy",
    "taped", "tapes", "tardo", "tardy", "tarot", "tasks", "taste", "tasty", "teach", "teams",
    "tears", "tease", "techs", "teeth", "tempo", "tenor", "tense", "tenth", "tents", "terms",
    "tests", "texts", "thank", "theft", "their", "theme", "there", "these", "thick", "thief",
    "thigh", "thing", "think", "third", "thong", "thorn", "those", "three", "threw", "throb",
    "throw", "thrum", "thuds", "thugs", "thumb", "thump", "thung", "thuya", "thyme", "tiara",
    "tibia", "ticks", "tidal", "tides", "tiers", "tiffs", "tiger", "tight", "tiled", "tiles",
    "tills", "tilth", "tilts", "timed", "timer", "times", "timid", "tinct", "tinds", "tined",
    "tines", "tinge", "tings", "tinny", "tints", "tipis", "tippy", "tipsy", "tired", "tires",
    "titan", "tithe", "title", "toads", "toady", "toast", "today", "toddy", "toffs", "tofus",
    "togas", "toils", "toked", "token", "tokes", "tolls", "tombac", "tombs", "tomes", "tonal",
    "toned", "toner", "tones", "toney", "tongs", "tonic", "tonne", "tools", "tooth", "toots",
    "topaz", "toped", "topee", "toper", "topes", "topic", "topoi", "topos", "toppy", "toque",
    "torah", "torcs", "tores", "toric", "torse", "torto", "torts", "torus", "total", "toted",
    "totem", "totes", "touch", "tough", "tours", "touse", "touts", "towed", "towel", "tower",
    "towie", "towns", "towny", "toxic", "toxin", "toyed", "toyer", "toyon", "toyos", "trace",
    "track", "tract", "trade", "trail", "train", "trait", "tramp", "trams", "trans", "traps",
    "trash", "trawl", "trays", "tread", "treat", "treed", "treen", "trees", "treks", "trend",
    "tress", "trets", "triad", "trial", "tribe", "tribs", "trice", "trick", "tried", "trier",
    "tries", "trigo", "trigs", "trike", "trill", "trims", "trine", "trios", "tripe", "trips",
    "trite", "troad", "troak", "trode", "trogs", "trois", "troll", "tromp", "trona", "trone",
    "troop", "trope", "troth", "trots", "trout", "trove", "trows", "troys", "truce", "truck",
    "trued", "truer", "trues", "trugs", "trull", "truly", "trump", "trunk", "truss", "trust",
    "truth", "tryer", "tryma", "tryps", "tryst", "tsars", "tsuba", "tubae", "tubal", "tubas",
    "tubby", "tubed", "tuber", "tubes", "tucks", "tudor", "tufts", "tufty", "tules", "tulip",
    "tulle", "tumid", "tummy", "tumor", "tunas", "tuned", "tuner", "tunes", "tungs", "tunic",
    "tunny", "tupik", "tuple", "tuque", "turco", "turds", "turfs", "turfy", "turks", "turns",
    "turps", "tushy", "tusks", "tutee", "tutor", "tutus", "tuxes", "tuyer", "twain", "twang",
    "twasp", "tweak", "tweed", "tweel", "tween", "tweer", "tweet", "twerp", "twice", "twixt",
    "under", "union", "unite", "unity", "until", "upper", "upset", "urban", "usage", "using",
    "valet", "value", "vapor", "vault", "venue", "virus", "visit", "vital", "voice", "vowel",
    "wafer", "waged", "wager", "wages", "wagon", "wahoo", "waifs", "wails", "wains", "wairs",
    "waist", "waits", "waive", "waked", "waken", "waker", "wakes", "waled", "waler", "wales",
    "walks", "walls", "wally", "waldo", "walrus", "waltz", "wands", "waned", "wanes", "waney",
    "wangs", "wanks", "wanly", "wanna", "wants", "wards", "wared", "wares", "warez", "warks",
    "warms", "warns", "warps", "warts", "warty", "washy", "wasps", "waspy", "waste", "wasts",
    "watch", "water", "watts", "waved", "waver", "waves", "wavey", "wawls", "waxed", "waxer",
    "waxes", "waxen", "wazir", "weald", "weals", "weans", "wears", "weary", "weave", "webby",
    "weber", "weeds", "weedy", "weeks", "weens", "weeny", "weeps", "weepy", "weest", "weets",
    "wefts", "weigh", "weird", "weirs", "wekas", "welch", "welds", "wells", "welly", "welsh",
    "welts", "wench", "wends", "wenny", "wests", "wetly", "whack", "whale", "whams", "whang",
    "whaps", "wharf", "whats", "wheal", "wheat", "wheel", "wheen", "wheep", "whelk", "whelm",
    "whelp", "whens", "where", "whet", "whews", "wheys", "which", "whids", "whiff", "whigs",
    "while", "whims", "whine", "whiny", "whips", "whipt", "whirl", "whirr", "whirs", "whish",
    "whisk", "whist", "white", "whits", "whity", "whizz", "whole", "whomp", "whoof", "whoop",
    "whoot", "whops", "whore", "whorl", "whort", "whose", "whoso", "whump", "young", "youth",
    "zebra", "zones"
]

VALID_WORDS = set(WORD_BANK)


def load_stats() -> Dict[str, any]:
    """Loads historical game statistics."""
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    # Return default empty stats
    return {
        "played": 0,
        "won": 0,
        "streak": 0,
        "max_streak": 0,
        "distribution": {str(i): 0 for i in range(1, 7)}
    }


def save_stats(stats: Dict[str, any]):
    """Saves game statistics to file."""
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=4)
    except Exception:
        pass


def show_stats():
    """Displays statistics dashboard in the terminal."""
    stats = load_stats()
    played = stats["played"]
    won = stats["won"]
    win_rate = (won / played * 100) if played > 0 else 0.0
    
    print("\n" + color_text("=== CLI WORDLE STATISTICS ===", CLR_CYAN + CLR_BOLD))
    print(f"Games Played : {color_text(str(played), CLR_BOLD)}")
    print(f"Win Rate     : {color_text(f'{win_rate:.1f}%', CLR_BOLD)}")
    print(f"Current Streak: {color_text(str(stats['streak']), CLR_BOLD)}")
    print(f"Max Streak   : {color_text(str(stats['max_streak']), CLR_BOLD)}")
    print("\n" + color_text("Guess Distribution:", CLR_BOLD))
    
    max_count = max(stats["distribution"].values()) if stats["distribution"].values() else 1
    if max_count == 0:
        max_count = 1
        
    for i in range(1, 7):
        count = stats["distribution"][str(i)]
        bar_len = int((count / max_count) * 20)
        bar = "█" * bar_len
        print(f"  {i} | {bar} {count}")
    print()


def evaluate_guess(guess: str, secret: str) -> List[Tuple[str, str]]:
    """Evaluates a guess against the secret word.
    
    Returns a list of tuples containing: (character, coloring_ansi_code)
    Handles duplicate letters properly (only highlights yellow for extra characters
    if the secret contains that many occurrences).
    """
    secret_list = list(secret)
    guess_list = list(guess)
    result_colors = [CLR_GRAY] * 5

    # Step 1: Find perfect matches (Green)
    for i in range(5):
        if guess_list[i] == secret_list[i]:
            result_colors[i] = CLR_GREEN
            secret_list[i] = None  # Consume character
            guess_list[i] = None

    # Step 2: Find misplaced matches (Yellow)
    for i in range(5):
        if guess_list[i] is not None:
            char = guess_list[i]
            if char in secret_list:
                result_colors[i] = CLR_YELLOW
                secret_list[secret_list.index(char)] = None  # Consume character

    # Format output pairs
    return [(guess[i], result_colors[i]) for i in range(5)]


def print_board(guesses: List[List[Tuple[str, str]]]):
    """Prints the current Wordle board."""
    print("\n" + "┌───┬───┬───┬───┬───┐")
    for i in range(6):
        if i < len(guesses):
            row_str = "│"
            for char, color in guesses[i]:
                row_str += f" {color} {char.upper()} {CLR_RESET}│"
            print(row_str)
        else:
            print("│   │   │   │   │   │")
        if i < 5:
            print("├───┼───┼───┼───┼───┤")
    print("└───┴───┴───┴───┴───┘\n")


def print_keyboard(letter_statuses: Dict[str, str]):
    """Prints the keyboard letters color-coded by their state."""
    rows = [
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm"
    ]
    print("Keyboard Status:")
    for row in rows:
        row_str = "  "
        for char in row:
            status = letter_statuses.get(char)
            if status == CLR_GREEN:
                row_str += f"{CLR_FG_GREEN}{char.upper()}{CLR_RESET} "
            elif status == CLR_YELLOW:
                row_str += f"{CLR_FG_YELLOW}{char.upper()}{CLR_RESET} "
            elif status == CLR_GRAY:
                row_str += f"{CLR_FG_GRAY}{char.upper()}{CLR_RESET} "
            else:
                row_str += f"{char.upper()} "
        print(row_str)
    print()


def update_keyboard_status(letter_statuses: Dict[str, str], feedback: List[Tuple[str, str]]):
    """Updates keyboard statuses based on guess feedback.
    
    Greens override Yellows, which override Grays.
    """
    for char, color in feedback:
        current_status = letter_statuses.get(char)
        if color == CLR_GREEN:
            letter_statuses[char] = CLR_GREEN
        elif color == CLR_YELLOW:
            if current_status != CLR_GREEN:
                letter_statuses[char] = CLR_YELLOW
        elif color == CLR_GRAY:
            if current_status not in (CLR_GREEN, CLR_YELLOW):
                letter_statuses[char] = CLR_GRAY


def main():
    parser = argparse.ArgumentParser(
        description="CLI Wordle - An interactive terminal Wordle game in pure Python."
    )
    parser.add_argument("-w", "--word", help="Provide a custom secret 5-letter word to guess (practice mode)")
    parser.add_argument("-s", "--stats", action="store_true", help="View historical game statistics and exit")

    args = parser.parse_args()

    if args.stats:
        show_stats()
        sys.exit(0)

    # Initialize secret word
    if args.word:
        secret_word = args.word.strip().lower()
        if len(secret_word) != 5 or not secret_word.isalpha():
            print(color_text("Error: Custom word must be exactly 5 letters long and contain only alphabetical characters.", CLR_RED))
            sys.exit(1)
        practice_mode = True
    else:
        secret_word = random.choice(WORD_BANK)
        practice_mode = False

    # Welcome Header
    print(color_text("┌───────────────────────────────────┐", CLR_CYAN))
    print(f"│  {color_text('WELCOME TO TERMINAL CLI WORDLE', CLR_BOLD)}   │")
    print(color_text("└───────────────────────────────────┘", CLR_CYAN))
    print("Rules: Guess the 5-letter word in 6 attempts.")
    print(f"Color Codes: {CLR_GREEN} G {CLR_RESET} Correct spot, {CLR_YELLOW} Y {CLR_RESET} Misplaced, {CLR_GRAY} X {CLR_RESET} Absent\n")

    guesses = []
    letter_statuses = {}
    win = False

    while len(guesses) < 6:
        print_keyboard(letter_statuses)
        print_board(guesses)
        
        prompt = f"Enter guess {len(guesses) + 1}/6: "
        guess = input(prompt).strip().lower()

        # Input Validation
        if len(guess) != 5:
            print(color_text("Error: Guess must be exactly 5 letters.", CLR_FG_YELLOW))
            continue
        if not guess.isalpha():
            print(color_text("Error: Guess must contain only letters.", CLR_FG_YELLOW))
            continue
        if guess not in VALID_WORDS:
            print(color_text("Error: Word not in dictionary.", CLR_FG_YELLOW))
            continue

        # Evaluate Guess
        feedback = evaluate_guess(guess, secret_word)
        guesses.append(feedback)
        update_keyboard_status(letter_statuses, feedback)

        if guess == secret_word:
            win = True
            break

    # Final Board Print
    print_board(guesses)

    if win:
        guess_count = len(guesses)
        print(color_text(f"Congratulations! You guessed the word in {guess_count} attempt(s)!", CLR_FG_GREEN + CLR_BOLD))
        
        # Save Stats (only for standard mode, not custom word)
        if not practice_mode:
            stats = load_stats()
            stats["played"] += 1
            stats["won"] += 1
            stats["streak"] += 1
            if stats["streak"] > stats["max_streak"]:
                stats["max_streak"] = stats["streak"]
            stats["distribution"][str(guess_count)] += 1
            save_stats(stats)
            show_stats()
    else:
        print(color_text(f"Game Over! The secret word was: {secret_word.upper()}", CLR_RED + CLR_BOLD))
        
        if not practice_mode:
            stats = load_stats()
            stats["played"] += 1
            stats["streak"] = 0
            save_stats(stats)
            show_stats()


if __name__ == "__main__":
    main()
