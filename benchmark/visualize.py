import json

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Read the JSON files
with open("benchmark/BenchmarkResults-cgraphlib.json", "r") as f:
    cgraphlib_data = json.load(f)

with open("benchmark/BenchmarkResults-pygraphlib.json", "r") as f:
    pygraphlib_data = json.load(f)


# Process the data
def process_data(data, library):
    processed = []
    for execution_type, results in data.items():
        for task_count, times in results.items():
            for time in times:
                processed.append(
                    {"Library": library, "Execution Type": execution_type, "Task Count": int(task_count), "Time": time}
                )
    return processed


cgraphlib_processed = process_data(cgraphlib_data, "cgraphlib")
pygraphlib_processed = process_data(pygraphlib_data, "pygraphlib")

# Combine the data
all_data = pd.DataFrame(cgraphlib_processed + pygraphlib_processed)

# Set up the plot style
sns.set_style("darkgrid")
plt.figure(figsize=(20, 20))

# 1. Violin plot
plt.subplot(2, 1, 1)
sns.violinplot(x="Execution Type", y="Time", hue="Library", data=all_data, palette="Set2")
plt.title("Comparison of Execution Times")
plt.ylim(0, 500)
plt.ylabel("Time (seconds)")

# 2. Heatmap
plt.subplot(2, 1, 2)
pivot_data = all_data.pivot_table(
    values="Time", index=["Execution Type", "Task Count"], columns="Library", aggfunc="mean"
)
diff_data = pivot_data["pygraphlib"] / pivot_data["cgraphlib"]
sns.heatmap(
    diff_data.unstack(level=0), annot=True, fmt=".2f", cmap=sns.color_palette("light:g", as_cmap=True), center=1.5
)
plt.title("Performance Difference (x faster for cgraphlib)")

plt.tight_layout()
plt.savefig("docs/benchmark_results.png", dpi=300, bbox_inches="tight")

# Generate html and markdown table
html_table = """
<table style="border-collapse: collapse; width: 100%;">
  <tr>
    <th style="border: 1px solid black; padding: 8px;">Execution Type</th>
    <th style="border: 1px solid black; padding: 8px;">Task Count</th>
    <th style="border: 1px solid black; padding: 8px;">cgraphlib Avg ± Std (s)</th>
    <th style="border: 1px solid black; padding: 8px;">pygraphlib Avg ± Std (s)</th>
    <th style="border: 1px solid black; padding: 8px;">cgraphlib x faster</th>
  </tr>
"""

markdown_table = "| Execution Type | Task Count | cgraphlib Time (s) | pygraphlib Time (s) | cgraphlib x faster |\n"
markdown_table += "|----------------|------------|-------------------|--------------------|--------------------|\n"

for exec_type in all_data["Execution Type"].unique():
    for task_count in all_data["Task Count"].unique():
        cg_data = all_data[
            (all_data["Execution Type"] == exec_type)
            & (all_data["Task Count"] == task_count)
            & (all_data["Library"] == "cgraphlib")
        ]["Time"]
        pg_data = all_data[
            (all_data["Execution Type"] == exec_type)
            & (all_data["Task Count"] == task_count)
            & (all_data["Library"] == "pygraphlib")
        ]["Time"]

        cg_avg, cg_std = cg_data.mean(), cg_data.std()
        pg_avg, pg_std = pg_data.mean(), pg_data.std()

        cg_x_faster = pg_avg / cg_avg

        # Use range of 1-3 to set the opacity between 0.3 and 0.8
        cg_x_opacity = min(max(0, (cg_x_faster - 1) / 2) + 0.3, 0.8)
        if cg_x_faster >= 1:
            cg_color = "background-color: rgba(144, 238, 144, 0.4);"  # Light green with 40% opacity
            pg_color = "background-color: rgba(255, 255, 224, 0.4);"  # Light yellow with 40% opacity
            cg_x_faster_color = (
                f"background-color: rgba(144, 238, 144, {cg_x_opacity});"  # Light green with 40% opacity
            )
        else:
            cg_color = "background-color: rgba(255, 255, 224, 0.4);"  # Light yellow with 40% opacity
            pg_color = "background-color: rgba(144, 238, 144, 0.4);"  # Light green with 40% opacity
            cg_x_faster_color = (
                f"background-color: rgba(255, 255, 224, {cg_x_opacity});"  # Light yellow with 40% opacity
            )

        html_table += f"""
        <tr>
            <td style="border: 1px solid black; padding: 8px;">{exec_type.capitalize()}</td>
            <td style="border: 1px solid black; padding: 8px;">{task_count}</td>
            <td style="border: 1px solid black; padding: 8px; {cg_color}">{cg_avg:.6f} ± {cg_std:.6f}</td>
            <td style="border: 1px solid black; padding: 8px; {pg_color}">{pg_avg:.6f} ± {pg_std:.6f}</td>
            <td style="border: 1px solid black; padding: 8px; {cg_x_faster_color}">{cg_x_faster:.2f}</td>
        </tr>
        """

        markdown_table += f"| {exec_type.capitalize()} | {task_count} | {cg_avg:.6f} ± {cg_std:.6f}|  {pg_avg:.6f} ± {pg_std:.6f} | {pg_avg / cg_avg:.2f} |\n"

html_table += "</table>"
print(markdown_table)

# Save the HTML table to a file
with open("docs/benchmark_results.html", "w") as f:
    f.write(html_table)

print("HTML table has been saved to 'docs/benchmark_results.html'")
