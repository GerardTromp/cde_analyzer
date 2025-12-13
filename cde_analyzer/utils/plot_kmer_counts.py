import pandas as pd # type: ignore
import matplotlib.pyplot as plt # type: ignore
import numpy as np
import math
from typing import List

def plot_kmer_counts(kmer_counts: pd.DataFrame, kmers: List, ax_limits: List[float], mincount=30):
    colors = ['skyblue', 'salmon', 'lightgreen']
    color_map = dict(zip([3,4,5], colors))
    # kmer_counts.hist(figsize=(10, 5));
    global_xmin = ax_limits[0]
    global_xmax = ax_limits[1]
    global_ymin = ax_limits[2]
    global_ymax = ax_limits[3]


    # Create subplots
    # fig, axes = plt.subplots(3, 2, figsize=(20, 10)) # 2 rows, 3 columns for 5 plots
    # axes = axes.flatten() # Flatten the 2D array of axes for easier iteration

    # Plot histograms and set limits

    # Enumerate the different k values.
    # Subset the data frame (k and count>x) and produce the histogram for each
    # 
    # for i in [3,4,5,6,7]:
    #     j = i - 3
    #     if j < len(axes): # Ensure we don't try to plot on non-existent axes
    #         ax = axes[j]
    #         df = kmer_counts[(kmer_counts['count']>30) & (kmer_counts['k']==i)][['count']]
    #         df.rename(columns={'count': f"k = {i}"}, inplace=True)
    #         df.hist(
    #             alpha=0.5, 
    #             bins=250, 
    #             sharex=True            
    #         )
    #         # df[col].hist(ax=ax, bins=250, edgecolor='black') # Use consistent bins for uniform column width
    #         ax.set_xlim(global_xmin, global_xmax)
    #         ax.set_ylim(0, global_ymax) # Set y-axis limits

    #         ax.set_title(f'Histogram of k = {i}')
    #         ax.set_xlabel('Value')
    #         ax.set_ylabel('Frequency')

    # # Hide any unused subplots if your layout has more axes than plots
    # for i in range(len([3,4,5,6,7]), len(axes)):
    #     fig.delaxes(axes[i])

    # plt.tight_layout() # Adjust subplot params for a tight layout
    # plt.show()



    # kmer_hist, axes = (
    #     kmer_counts[(kmer_counts['count']>30) & (kmer_counts['k']>5)])[['k','count']].hist(
    #         figsize=(15,8), 
    #         column="count", 
    #         alpha=0.5, 
    #         bins=250, 
    #         by='k', 
    #         sharex=True
    #     );
    # axes = axes.flatten()

    # # Iterate through each subplot and set the x-limits
    # for ax in axes:
    #     ax.set_xlim(min_xlim, max_xlim)

    # plt.show()


    bin_width = 5
    bins = np.arange(global_xmin, global_xmax + bin_width, bin_width)

    # The k values you want histograms for
    ks = kmers
    ks_cnt = len(ks)
    
    if ks_cnt > 3:
        nrows =  math.ceil(ks_cnt/3)
        ncols = 3
    
    # Create a row of subplots (adjust ncols if you want a grid layout instead)
    fig, axs = plt.subplots(nrows=nrows, ncols=ncols, figsize=(18, 4*nrows), sharex=True, sharey=True)
    

    # In case axes is a single object (when len(ks) == 1), make it iterable
    if len(ks) == 1:
        axflat = [axs]
    else:
        axflat = axs.flatten()  # type: ignore

    def get_histogram_frequencies(group: pd.DataFrame):
        # Use pd.cut to assign each value to a bin
        binned_values = pd.cut(group['count'], bins=bins, right=False) # type: ignore
        # Count the frequencies of each bin
        
        return binned_values.value_counts().sort_index()

    # global_ymax = 0
    # # df = kmer_counts[(kmer_counts['count'] > mincount) & (kmer_counts['k'] == kmers[i])][['count']]
    # df = kmer_counts[['k','count']]
    # # df = df[df['count']>mincount]
    # histogram_tables = df.set_index('k').groupby('k').apply(get_histogram_frequencies)
    # row_totals = histogram_tables.sum(axis=1) # type: ignore
    # # Need to incorporate mincount -- see above
    # # histogram_tables = histogram_tables.drop(columns=histogram_tables.columns[[0,1,3,4]])
    # # print(row_totals)
    # # print(histogram_tables)
    # df_normalized = histogram_tables.div(row_totals, axis=0)
    # print(f"\nNormalized:\n{df_normalized}\n\n")
    # df_max = df_normalized.max().max()
    # print(df_max)
    # global_ymax = max(global_ymax, df_max)*1.10
    # print(global_ymax)
    

    # for j, k in enumerate(ks):
    for j in range(nrows):
        for k in range(ncols):
            i = j * ncols + k
            ax = axs[j,k]
            
        # ax = axs[j]

        # Filter data for this k
            if i >= len(kmers):
                continue
            # print(f"Iterate through subplots: i: {i:2d}, j: {j:2d}, k: {k:2d}, len kmers: {len(kmers):2d}, kmer: {kmers[i]:2d}")
            df = kmer_counts[(kmer_counts['count'] > mincount) & (kmer_counts['k'] == kmers[i])][['count']]
            df.rename(columns={'count': f"k = {kmers[i]}"}, inplace=True)
            # print(df.head())

        # --- Option 1: matplotlib hist (recommended for control) ---
            values = df.iloc[:, 0]
            clipped = values[(values >= global_xmin) & (values <= global_xmax)]
            ax.hist(clipped, bins=bins, density=True, alpha=0.5, edgecolor="black") # type: ignore

        # --- Option 2: pandas hist ---
        # df.hist(alpha=0.5, bins=250, ax=ax)

        # Apply consistent limits
            ax.set_xlim(global_xmin, global_xmax) # type: ignore
            # ax.set_ylim(global_ymin, global_ymax) # type: ignore

        # Labels and title
            ax.set_title(f'k = {kmers[i]}') # type: ignore
            ax.set_xlabel('Value') # type: ignore
            if k == 0:  # only label y-axis on first subplot to save space
                ax.set_ylabel('Density') # type: ignore

    # Tight layout so things don’t overlap
    plt.tight_layout()
    # Need filename as argument
    plt.savefig("test1.png", dpi=300)
    # plt.show()
    
    return fig, axs