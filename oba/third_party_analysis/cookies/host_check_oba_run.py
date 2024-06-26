import json
import os
import sqlite3
import pandas as pd
from adblockparser import AdblockRules
import time
from tqdm import tqdm
import tldextract
import csv

# OBA_RUN
EXPERIMENT_DIR = "/Volumes/LaCie/OpenOBA/oba_runs/"
experiment_name = "style_and_fashion_experiment_do_nothing"
oba_db_path = f"{EXPERIMENT_DIR}/{experiment_name}/crawl-data-copy.sqlite"
experiment_json = f"{EXPERIMENT_DIR}/{experiment_name}/{experiment_name}_config.json"
markdown_file = (
    f"{EXPERIMENT_DIR}/{experiment_name}/results/cookies_third_party_metrics.md"
)
# Get browser_ids from the JSON file
with open(experiment_json, "r") as f:
    experiment_config = json.load(f)
    browser_ids_order = experiment_config["browser_ids"]["oba"]

csv_file = f"{EXPERIMENT_DIR}/{experiment_name}/results/cookies_host_check.csv"


def get_domains_data(group):
    # Step 1: Further filter to get only 3rd party tracking entries
    tracking_df = group[
        group["third_party"]
        & (group["easyprivacy"] | group["easylist"] | group["adserverlist"])
    ]

    # Step 2: Collect sets of domains for each session
    domain_sets = tracking_df.groupby("browser_id")["host_domain"].apply(set)

    # Step 3: Find the intersection of all domain sets
    common_domains = (
        set.intersection(*domain_sets.values) if len(domain_sets) > 0 else set()
    )

    common_domains

    # Step 3: Count occurrences of each domain
    domain_counts = tracking_df["host_domain"].value_counts()

    # Make a DataFrame with the domain, the count, and the percentage of the total requests
    domain_counts = pd.DataFrame(domain_counts).reset_index()
    domain_counts.columns = ["Domain", "Count"]
    domain_counts["Percentage"] = domain_counts["Count"] / len(tracking_df) * 100
    # Add a column with the cumulative percentage
    domain_counts["Cumulative Percentage"] = domain_counts["Percentage"].cumsum()

    # Step 4: Get the top 10 domains
    # top_10_domains = domain_counts

    return domain_counts, common_domains


# First we need to connect the database
conn = sqlite3.connect(oba_db_path)

# Open files to get the block lists

# First get the actual absolute path of the script
script_path = os.path.abspath(__file__)
script_dir = os.path.dirname(script_path)
with open(f"{script_dir}/tracking_lists/easyprivacy-justdomains.txt") as f:
    easyprivacy_list = f.read().splitlines()
with open(f"{script_dir}/tracking_lists/easylist-justdomains.txt") as f:
    easylist_list = f.read().splitlines()
with open(f"{script_dir}/tracking_lists/adserverlist-justdomains.txt") as f:
    adserverlist_list = f.read().splitlines()

# Query all the cookies from the database with browser_id and host ordered by id
query = """
    SELECT c.id as id,
        c.host as host,
        c.name as name,
        c.value as value,
        c.browser_id as browser_id,
        sv.site_url as visit_url,
        (sv.site_rank IS NOT NULL) AS control_visit  
    FROM javascript_cookies c
    JOIN site_visits sv ON c.visit_id = sv.visit_id
    ORDER BY c.id
    """

# Execute the query
cursor = conn.cursor()
cursor.execute(query)

# Get all the cookies to a DataFrame
df_cookies = pd.DataFrame(
    cursor.fetchall(),
    columns=["id", "host", "name", "value", "browser_id", "visit_url", "control_visit"],
)

# Close the connection
conn.close()

# Change control_visit to boolean
df_cookies["control_visit"] = df_cookies["control_visit"].astype(bool)

# Create a set with the unique hosts
# Add the host_domain and visit_url_domain to the DataFrame
df_cookies["host_domain"] = df_cookies["host"].apply(
    lambda x: tldextract.extract(x).registered_domain
)
unique_hosts_domain = set(df_cookies["host_domain"])
block_results = {}

# Evaluate the rules for each host
start_time = time.time()
print(
    f"Starting Tracking Evaluation processing for {len(unique_hosts_domain)} hosts..."
)
for host_domain in tqdm(unique_hosts_domain):
    # easyprivacy_result = easyprivacy_rules.should_block(host, rule_params)
    # easylist_result = easylist_rules.should_block(host, rule_params)
    # adserverlist_result = adserverlist_rules.should_block(host, rule_params)
    # block_results[host] = [easyprivacy_result, easylist_result, adserverlist_result]

    block_results[host_domain] = [
        host_domain in easyprivacy_list,
        host_domain in easylist_list,
        host_domain in adserverlist_list,
    ]
end_time = time.time()


print(
    f"Finished evaluating all unique HOSTS after {end_time - start_time:.2f} seconds."
)


df_cookies["easyprivacy"] = df_cookies["host_domain"].apply(
    lambda x: block_results[x][0]
)
df_cookies["easylist"] = df_cookies["host_domain"].apply(lambda x: block_results[x][1])
df_cookies["adserverlist"] = df_cookies["host_domain"].apply(
    lambda x: block_results[x][2]
)

# Check for third-party cookies
df_cookies["visit_url_domain"] = df_cookies["visit_url"].apply(
    lambda x: tldextract.extract(x).registered_domain
)

df_cookies["third_party"] = df_cookies["host_domain"] != df_cookies["visit_url_domain"]

# Write the DataFrame to a CSV file
df_cookies.to_csv(csv_file, index=False)

# Perform groupby and aggregate operations
grouped_df = df_cookies.groupby("browser_id")

# Create a new DataFrame to store results
results_table = pd.DataFrame(
    {
        # Unique combinations of host-name-value
        "NumUniqueCookies": grouped_df.apply(
            lambda x: x.drop_duplicates(subset=["host", "name", "value"]).shape[0]
        ),
        # Unique combinations of host-name-value with third-party cookies
        "NumUniqueCookies_3rdParty": grouped_df.apply(
            lambda x: x[x["third_party"]]
            .drop_duplicates(subset=["host", "name", "value"])
            .shape[0]
        ),
        # Unique combinations of host-name-value with third-party cookies and any filter list true
        "NumUniqueCookies_3rdParty_Tracking": grouped_df.apply(
            lambda x: x[
                x["easyprivacy"] | x["easylist"] | x["adserverlist"] & x["third_party"]
            ]
            .drop_duplicates(subset=["host", "name", "value"])
            .shape[0]
        ),
        "NumUniqueCookiesDomains": grouped_df.apply(
            lambda x: x.drop_duplicates(subset=["host_domain"]).shape[0]
        ),
        "NumUniqueCookiesDomains_3rdParty": grouped_df.apply(
            lambda x: x[x["third_party"]]
            .drop_duplicates(subset=["host_domain"])
            .shape[0]
        ),
        "NumUniqueCookiesDomains_3rdParty_Tracking": grouped_df.apply(
            lambda x: x[
                x["easyprivacy"] | x["easylist"] | x["adserverlist"] & x["third_party"]
            ]
            .drop_duplicates(subset=["host_domain"])
            .shape[0]
        ),
    }
)

# Reset index if necessary to make 'browser_id' a column again
results_table.reset_index(inplace=True)

results_table["browser_id"] = pd.Categorical(
    results_table["browser_id"], categories=browser_ids_order, ordered=True
)

results_table = results_table.sort_values("browser_id")

# Exclude row with browser_id = 0
results_table = results_table[
    results_table["browser_id"].isin(browser_ids_order)
].reset_index(drop=True)


# From results_table, get the total number of cookies for the first 6 rows
first_6_rows = df_cookies[df_cookies["browser_id"].isin(browser_ids_order[:6])]
summary_data = {
    "browser_id": "-",
    "NumUniqueCookies": first_6_rows.drop_duplicates(
        subset=["host", "name", "value"]
    ).shape[0],
    "NumUniqueCookies_3rdParty": first_6_rows[first_6_rows["third_party"]]
    .drop_duplicates(subset=["host", "name", "value"])
    .shape[0],
    "NumUniqueCookies_3rdParty_Tracking": first_6_rows[
        first_6_rows["third_party"]
        & (
            first_6_rows["easyprivacy"]
            | first_6_rows["easylist"]
            | first_6_rows["adserverlist"]
        )
    ]
    .drop_duplicates(subset=["host", "name", "value"])
    .shape[0],
    "NumUniqueCookiesDomains": first_6_rows.drop_duplicates(
        subset=["host_domain"]
    ).shape[0],
    "NumUniqueCookiesDomains_3rdParty": first_6_rows[first_6_rows["third_party"]]
    .drop_duplicates(subset=["host_domain"])
    .shape[0],
    "NumUniqueCookiesDomains_3rdParty_Tracking": first_6_rows[
        first_6_rows["third_party"]
        & (
            first_6_rows["easyprivacy"]
            | first_6_rows["easylist"]
            | first_6_rows["adserverlist"]
        )
    ]
    .drop_duplicates(subset=["host_domain"])
    .shape[0],
}

# Convert to DataFrame for a single row result
summary_row = pd.DataFrame([summary_data], index=["Combined First 6 Sessions"])

# Append this summary row to the results_table
results_table = pd.concat([results_table, summary_row])

# OBTAIN THE TOP 10 DOMAINS AND THE OVERLAP OF 3RD PARTY TRACKING DOMAINS IN THE FIRST 6 SESSIONS
top_10_domains, common_domains = get_domains_data(
    df_cookies[df_cookies["browser_id"].isin(browser_ids_order[:6])]
)
# Create a row with the same shape as the results_table but with - for all values except the NumUniqueCookiesDomains_3rdParty_Tracking column which will contain the number of common domains
common_domains_row = pd.DataFrame(
    [
        {
            "browser_id": "-",
            "NumUniqueCookiesDomains_3rdParty_Tracking": len(common_domains),
        }
    ],
    index=["Common 3rd Party Tracking Domains in First 6 Sessions"],
)

# Append this row to the results_table
results_table = pd.concat([results_table, common_domains_row])
results_table_markdown = results_table.to_markdown()


# Now repeat everything but considering an additional 'control_visit' filter = True

# Create a new DataFrame to store results
control_results_table = pd.DataFrame(
    {
        # Unique combinations of host-name-value
        "ControlVisits_NumUniqueCookies": grouped_df.apply(
            lambda x: x[x["control_visit"]]
            .drop_duplicates(subset=["host", "name", "value"])
            .shape[0]
        ),
        # Unique combinations of host-name-value with third-party cookies
        "ControlVisits_NumUniqueCookies_3rdParty": grouped_df.apply(
            lambda x: x[x["control_visit"] & x["third_party"]]
            .drop_duplicates(subset=["host", "name", "value"])
            .shape[0]
        ),
        # Unique combinations of host-name-value with third-party cookies and any filter list true
        "ControlVisits_NumUniqueCookies_3rdParty_Tracking": grouped_df.apply(
            lambda x: x[
                x["control_visit"]
                & x["third_party"]
                & (x["easyprivacy"] | x["easylist"] | x["adserverlist"])
            ]
            .drop_duplicates(subset=["host", "name", "value"])
            .shape[0]
        ),
        "ControlVisits_NumUniqueCookiesDomains": grouped_df.apply(
            lambda x: x[x["control_visit"]]
            .drop_duplicates(subset=["host_domain"])
            .shape[0]
        ),
        "ControlVisits_NumUniqueCookiesDomains_3rdParty": grouped_df.apply(
            lambda x: x[x["control_visit"] & x["third_party"]]
            .drop_duplicates(subset=["host_domain"])
            .shape[0]
        ),
        "ControlVisits_NumUniqueCookiesDomains_3rdParty_Tracking": grouped_df.apply(
            lambda x: x[
                x["control_visit"]
                & x["third_party"]
                & (x["easyprivacy"] | x["easylist"] | x["adserverlist"])
            ]
            .drop_duplicates(subset=["host_domain"])
            .shape[0]
        ),
    }
)

# Reset index if necessary to make 'browser_id' a column again
control_results_table.reset_index(inplace=True)

control_results_table["browser_id"] = pd.Categorical(
    control_results_table["browser_id"], categories=browser_ids_order, ordered=True
)

control_results_table = control_results_table.sort_values("browser_id")

# Exclude row with browser_id = 0
control_results_table = control_results_table[
    control_results_table["browser_id"].isin(browser_ids_order)
].reset_index(drop=True)

# From results_table, get the total number of cookies for the first 6 rows
first_6_rows_control = df_cookies[
    df_cookies["browser_id"].isin(browser_ids_order[:6]) & df_cookies["control_visit"]
]
control_summary_data = {
    "browser_id": "-",
    "ControlVisits_NumUniqueCookies": first_6_rows_control.drop_duplicates(
        subset=["host", "name", "value"]
    ).shape[0],
    "ControlVisits_NumUniqueCookies_3rdParty": first_6_rows_control[
        first_6_rows_control["third_party"]
    ]
    .drop_duplicates(subset=["host", "name", "value"])
    .shape[0],
    "ControlVisits_NumUniqueCookies_3rdParty_Tracking": first_6_rows_control[
        first_6_rows_control["third_party"]
        & (
            first_6_rows_control["easyprivacy"]
            | first_6_rows_control["easylist"]
            | first_6_rows_control["adserverlist"]
        )
    ]
    .drop_duplicates(subset=["host", "name", "value"])
    .shape[0],
    "ControlVisits_NumUniqueCookiesDomains": first_6_rows_control.drop_duplicates(
        subset=["host_domain"]
    ).shape[0],
    "ControlVisits_NumUniqueCookiesDomains_3rdParty": first_6_rows_control[
        first_6_rows_control["third_party"]
    ]
    .drop_duplicates(subset=["host_domain"])
    .shape[0],
    "ControlVisits_NumUniqueCookiesDomains_3rdParty_Tracking": first_6_rows_control[
        first_6_rows_control["third_party"]
        & (
            first_6_rows_control["easyprivacy"]
            | first_6_rows_control["easylist"]
            | first_6_rows_control["adserverlist"]
        )
    ]
    .drop_duplicates(subset=["host_domain"])
    .shape[0],
}

# Convert to DataFrame for a single row result
control_summary_row = pd.DataFrame(
    [control_summary_data], index=["Combined First 6 Sessions"]
)

# Append this summary row to the results_table
control_results_table = pd.concat([control_results_table, control_summary_row])

# OBTAIN THE OVERLAP OF 3RD PARTY TRACKING DOMAINS IN THE FIRST 6 SESSIONS
top_10_domains_control, common_domains_control = get_domains_data(
    df_cookies[
        df_cookies["browser_id"].isin(browser_ids_order[:6])
        & df_cookies["control_visit"]
    ]
)
# Create a row with the same shape as the results_table but with - for all values except the ControlVisits_NumUniqueCookiesDomains_3rdParty_Tracking column which will contain the number of common domains
common_domains_control_row = pd.DataFrame(
    [
        {
            "browser_id": "-",
            "ControlVisits_NumUniqueCookiesDomains_3rdParty_Tracking": len(
                common_domains_control
            ),
        }
    ],
    index=["Common 3rd Party Tracking Domains in First 6 Sessions"],
)

# Append this row to the control_results_table
control_results_table = pd.concat([control_results_table, common_domains_control_row])

control_results_table_markdown = control_results_table.to_markdown()

results_table_markdown = results_table.to_markdown()
control_results_table_markdown = control_results_table.to_markdown()

# # To save to a Markdown file
with open(markdown_file, "w") as f:
    f.write("## Cookies Metrics\n")
    f.write(results_table_markdown)
    f.write("\n\n")
    f.write("## Overlap of 3rd Party Tracking Domains in First 6 Sessions\n")
    f.write(", \n".join(list(common_domains)))
    f.write("\n\n")
    f.write("## Top 10 3rd Party Tracking Domains in First 6 Sessions\n")
    f.write(top_10_domains.to_markdown())
    f.write("\n\n")
    f.write("## Control Visits Only Cookies Metrics\n")
    f.write(control_results_table_markdown)
    f.write("\n\n")
    f.write("## Overlap of 3rd Party Tracking Domains in First 6 Sessions\n")
    f.write(", \n".join(list(common_domains_control)))
    f.write("\n\n")
    f.write(
        "## Top 10 3rd Party Tracking Domains in First 6 Sessions (Control Visits Only)\n"
    )
    f.write(top_10_domains_control.to_markdown())

print(f"FINISHED FOR {experiment_name}!")
