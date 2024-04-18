import requests
from adblockparser import AdblockRules
import csv
import time
from tqdm import tqdm

# EXPERIMENT IN VOLUME
# EXPERIMENT_NAME = "style_and_fashion_experiment_do_nothing"
# EXPERIMENT_DIR = f"/Volumes/FOBAM_data/8_days/datadir/{EXPERIMENT_NAME}/"


# Experiment in local
# EXPERIMENT_NAME = "control_run_reject"
# EXPERIMENT_DIR = f"/Users/mateoormeno/Desktop/control_runs/{EXPERIMENT_NAME}/"

# Single file
EXPERIMENT_DIR = (
    f"/Users/mateoormeno/Desktop/control_runs/style_and_fashion_experiment_reject/"
)

print(f"Fetching rules")
start_time = time.time()

easyprivacy_url = "https://easylist.to/easylist/easyprivacy.txt"
easyprivacy_content = requests.get(easyprivacy_url).text

easylist_url = "https://easylist.to/easylist/easylist.txt"
easylist_content = requests.get(easylist_url).text

adserverlist_url = "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext"
adserverlist_content = requests.get(adserverlist_url).text

easyprivacy_rules = AdblockRules(easyprivacy_content.splitlines())
easylist_rules = AdblockRules(easylist_content.splitlines())
adserverlist_rules = AdblockRules(adserverlist_content.splitlines())

end_time = time.time()
print(f"Fetched all rules in {end_time - start_time:.2f} seconds.")

rule_params = {"third-party": True}

http_requests_file = f"{EXPERIMENT_DIR}/results/javascript_script_url.txt"

# Open the file and read the URLs
with open(http_requests_file, "r") as file:
    javascript_script_url = file.read().splitlines()

# Create set with unique URLs
unique_urls = set(javascript_script_url)
block_results = {}

# Evaluate the rules for each URL
start_time = time.time()
print(f"Starting Third Party Evaluation processing for {len(unique_urls)} URLs...")
for url in tqdm(unique_urls):
    easyprivacy_result = easyprivacy_rules.should_block(url, rule_params)
    easylist_result = easylist_rules.should_block(url, rule_params)
    adserverlist_result = adserverlist_rules.should_block(url, rule_params)
    block_results[url] = [easyprivacy_result, easylist_result, adserverlist_result]
end_time = time.time()

print(
    f"Finished evaluating all unique JAVASCRIPT SCRIPT URLs after {end_time - start_time:.2f} seconds."
)

# For each URL, write the results to a CSV file
csv_file = f"{EXPERIMENT_DIR}/results/javascript_script_url.csv"
print(f"Writing results to {csv_file}...")
with open(csv_file, "w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["url", "easyprivacy", "easylist", "adserverlist"])
    for url in tqdm(javascript_script_url):
        easyprivacy_result = block_results[url][0]
        easylist_result = block_results[url][1]
        adserverlist_result = block_results[url][2]
        writer.writerow([url, easyprivacy_result, easylist_result, adserverlist_result])

end_processing_time = time.time()
print(
    f"All URLs processed. Total runtime: {end_processing_time - start_time:.2f} seconds."
)
