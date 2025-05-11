import os
import requests
import hashlib
import unicodedata
import multiprocessing
import time
from bs4 import BeautifulSoup

# === CONFIGURATION ===
INPUT_DIR = "./input_files"
NAME_FILE = "./names.txt"
SURNAME_FILE = "./surnames.txt"
OUTPUT_DIR = "./output_files"
CHECKPOINT_FILE = "checkpoint.txt"
SEPARATORS = [".", "_", "-", "~", "", "__", "--"]
MAX_USERNAME_LENGTH = 32
HASH_TYPE = None  # Set to 'md5', 'sha1', 'sha256', or 'ntlm' to enable hashing
NUM_PROCESSES = multiprocessing.cpu_count()
BATCH_SIZE = 2000
SIMILARITY_THRESHOLD = 0.8  # Threshold for avoiding too similar names or words

# === HELPERS ===
def normalize_unicode(text):
    """Normalize text to ASCII and lowercase."""
    return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode().lower()


def to_leet(text):
    """Convert text to leetspeak (e.g., 's' -> '5', 'o' -> '0')."""
    return text.translate(str.maketrans("aeiost", "431057"))


def hash_text(text, algo):
    """Generate hash for a given text using specified algorithm."""
    raw = text.encode('utf-16le') if algo == 'ntlm' else text.encode()
    if algo == 'md5':
        return hashlib.md5(raw).hexdigest()
    elif algo == 'sha1':
        return hashlib.sha1(raw).hexdigest()
    elif algo == 'sha256':
        return hashlib.sha256(raw).hexdigest()
    elif algo == 'ntlm':
        return hashlib.new('md4', raw).hexdigest()
    return text


def read_file(path):
    """Read and return lines from a file."""
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def read_checkpoint():
    """Read the last processed entry from the checkpoint file."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return f.read().strip()
    return ""


def write_checkpoint(last_processed):
    """Write the last processed entry to the checkpoint file."""
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(last_processed)


# === SMART GATHERING FUNCTIONS ===
def fetch_cool_words():
    """Fetch cool words from multiple sources intelligently."""
    cool_words = set()

    # Scrape words from a random word generator website
    try:
        url = "https://www.randomlists.com/random-words?qty=100"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for word in soup.find_all("li", class_="random_word"):
            word_text = word.get_text(strip=True).lower()
            if len(word_text) > 3:  # Filter out very short words
                cool_words.add(word_text)
    except requests.RequestException:
        pass

    # Scrape from a synonym source to get diverse words
    try:
        url = "https://www.thesaurus.com/browse/random"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for word in soup.find_all("a", class_="css-1gybfto e1ccqdb60"):
            word_text = word.get_text(strip=True).lower()
            if len(word_text) > 3:
                cool_words.add(word_text)
    except requests.RequestException:
        pass

    return cool_words


def fetch_names():
    """Fetch a list of names from multiple sources intelligently."""
    names = set()

    # Fetch names from a random name generator
    try:
        url = "https://www.fakenamegenerator.com/gen-random-us-us.php"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for name in soup.find_all("div", class_="address"):
            name_text = name.get_text(strip=True).split(' ')[0]
            if name_text and len(name_text) > 2:  # Filter out too short names
                names.add(name_text.lower())
    except requests.RequestException:
        pass

    # Scrape a list of popular first names
    try:
        url = "https://www.names.org/lists/popular-baby-names/"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for name in soup.find_all("div", class_="grid-x grid-padding-x"):
            name_text = name.get_text(strip=True)
            if name_text and len(name_text) > 2:
                names.add(name_text.lower())
    except requests.RequestException:
        pass

    return names


def fetch_surnames():
    """Fetch a list of surnames from multiple sources intelligently."""
    surnames = set()

    # Scrape surnames from a public domain list
    try:
        url = "https://www.surnamedb.com/"
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        for surname in soup.find_all("div", class_="surname"):
            surname_text = surname.get_text(strip=True)
            if surname_text and len(surname_text) > 2:
                surnames.add(surname_text.lower())
    except requests.RequestException:
        pass

    return surnames


# === WORKER FUNCTION ===
def worker(names, surnames, seen, lock, output_dir, checkpoint_name, checkpoint_surname):
    """Worker function to generate and write usernames to files in parallel."""
    all_variants = []
    for name in names:
        for surname in surnames:
            if name < checkpoint_name or (name == checkpoint_name and surname < checkpoint_surname):
                continue
            variants = generate_variants(name, surname)
            all_variants.extend(variants)
            write_checkpoint(f"{name},{surname}")  # Update progress after each name-surname pair

    # Write variants to output files (sorting before writing)
    all_variants = sorted(set(all_variants))  # Remove duplicates and sort
    formal_usernames = [v for v in all_variants if "." in v]  # Formal: name.surname
    gamer_usernames = [v for v in all_variants if not "." in v]  # Gamer-style: Dread_X, IceBlaze08, etc.

    # Check if the word already exists in the file to prevent duplicates
    def write_unique_file(filename, usernames):
        """Write unique usernames to file by checking for duplicates."""
        existing_usernames = set(read_file(filename))
        with open(filename, "a", encoding="utf-8") as f:
            for username in usernames:
                if username not in existing_usernames:
                    f.write(f"{username}\n")
                    existing_usernames.add(username)

    # Write formal usernames to file
    write_unique_file(os.path.join(output_dir, "formal_usernames.txt"), formal_usernames)

    # Write gamer usernames to file
    write_unique_file(os.path.join(output_dir, "gamer_usernames.txt"), gamer_usernames)


# === MAIN COMBINE FUNCTION ===
def combine():
    """Main function to combine name-surname pairs into usernames, write to files, and track progress."""
    names = fetch_names()  # Fetching names from the web
    surnames = fetch_surnames()  # Fetching surnames from the web
    cool_words = fetch_cool_words()  # Fetch cool words from the web
    seen = multiprocessing.Manager().dict()
    lock = multiprocessing.Lock()

    last_checkpoint = read_checkpoint()
    if last_checkpoint:
        checkpoint_name, checkpoint_surname = last_checkpoint.split(',')
    else:
        checkpoint_name, checkpoint_surname = "", ""

    # Process names in chunks for parallel processing
    chunk_size = max(1, len(names) // NUM_PROCESSES)
    chunks = [names[i:i + chunk_size] for i in range(0, len(names), chunk_size)]

    processes = []
    for chunk in chunks:
        p = multiprocessing.Process(target=worker, args=(chunk, surnames, seen, lock, OUTPUT_DIR, checkpoint_name, checkpoint_surname))
        p.start()
        processes.append(p)

    # Wait for all processes to finish
    for p in processes:
        p.join()

    print("Username generation completed!")


if __name__ == "__main__":
    # Ensure output directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Start the username generation process
    combine()
