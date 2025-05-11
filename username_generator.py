# === username_generator.py ===
import os
import hashlib
import unicodedata
import multiprocessing

# === CONFIG ===
INPUT_DIR = "./input"
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NAME_FILE = os.path.join(INPUT_DIR, "names.txt")
SURNAME_FILE = os.path.join(INPUT_DIR, "surnames.txt")
PETS_FILE = os.path.join(INPUT_DIR, "pets.txt")
WORDS_FILE = os.path.join(INPUT_DIR, "words.txt")
YEARS_FILE = os.path.join(INPUT_DIR, "years.txt")

SEPARATORS = [".", "_", "-", "~", "", "__", "--"]
MAX_LENGTH = 32

# === HELPERS ===
def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip().lower() for line in f if line.strip()]

def normalize(text):
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()

def to_leet(text):
    return text.translate(str.maketrans("aeiost", "431057"))

def build_suffixes(pet_names, years, words):
    suffixes = []
    for year in years:
        suffixes.append(year)
    for word in words:
        suffixes.append(word)
        suffixes.append(to_leet(word))
    for pet in pet_names:
        suffixes.append(pet)
    return list(set(suffixes))

def format_and_limit(username):
    return username[:MAX_LENGTH].lower()

# === GENERATION ===
def generate_usernames(name, surname, suffixes):
    results = {
        "formal": set(),
        "neutral": set(),
        "gamer": set()
    }

    name = normalize(name)
    surname = normalize(surname)
    initial_n, initial_s = name[0], surname[0]

    base_variants = [
        (name, surname),
        (surname, name),
        (initial_n, surname),
        (name, initial_s),
        (initial_n, initial_s),
        (to_leet(name), to_leet(surname)),
        (name, ""),
        (surname, "")
    ]

    for a, b in base_variants:
        for sep in SEPARATORS:
            base = format_and_limit(f"{a}{sep}{b}")
            if "." in sep or sep == "":
                results["formal"].add(base)
            else:
                results["neutral"].add(base)

            # Add suffix variations
            for suffix in suffixes:
                combined = format_and_limit(f"{base}{suffix}")
                results["neutral"].add(combined)

                gamer_style = f"{sep}{to_leet(a)}{sep}{suffix}{sep}"
                gamer_style = format_and_limit(gamer_style)
                results["gamer"].add(gamer_style)

    return results

# === MULTIPROCESSING WORKER ===
def worker(chunk, surnames, suffixes, out_q):
    result = {"formal": set(), "neutral": set(), "gamer": set()}
    for name in chunk:
        for surname in surnames:
            categories = generate_usernames(name, surname, suffixes)
            for cat in result:
                result[cat].update(categories[cat])
    out_q.put(result)

# === MAIN ===
def combine():
    print("[*] Loading inputs...")
    names = read_file(NAME_FILE)
    surnames = read_file(SURNAME_FILE)
    pets = read_file(PETS_FILE)
    words = read_file(WORDS_FILE)
    years = read_file(YEARS_FILE)
    suffixes = build_suffixes(pets, years, words)

    result_queue = multiprocessing.Queue()
    num_proc = multiprocessing.cpu_count()
    chunk_size = max(1, len(names) // num_proc)
    chunks = [names[i:i+chunk_size] for i in range(0, len(names), chunk_size)]

    print("[*] Starting generation with multiprocessing...")
    processes = []
    for chunk in chunks:
        p = multiprocessing.Process(target=worker, args=(chunk, surnames, suffixes, result_queue))
        p.start()
        processes.append(p)

    all_results = {"formal": set(), "neutral": set(), "gamer": set()}
    for _ in processes:
        result = result_queue.get()
        for k in all_results:
            all_results[k].update(result[k])

    for p in processes:
        p.join()

    print("[*] Writing sorted results to output directory...")
    for cat, entries in all_results.items():
        path = os.path.join(OUTPUT_DIR, f"{cat}.txt")
        with open(path, "w", encoding="utf-8") as f:
            for line in sorted(entries):
                f.write(line + "\n")

    print("[✓] Username generation complete.")

if __name__ == "__main__":
    combine()
