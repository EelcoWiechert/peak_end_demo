import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import mpld3
from mpld3 import plugins

def make_plot():
    # Make some fake data.
    a =  np.arange(0, 3, .02)

    # Create plots with pre-defined labels.
    fig, ax = plt.subplots()
    ax.plot(a)
    plot = mpld3.fig_to_html(fig)

    return plot