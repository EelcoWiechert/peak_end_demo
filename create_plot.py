import matplotlib.pyplot as plt
import mpld3

def make_plot(data,features_to_plot):

    variables_to_plot = dict()
    for item in features_to_plot[:-1]:
        variables_to_plot[item] = []

    # Create plots with pre-defined labels.
    fig, ax = plt.subplots()

    for feature, values in variables_to_plot.items():
        for track in data:
            values.append(track[feature])
        ax.plot(values, label=feature)
    ax.legend()
    plot = mpld3.fig_to_html(fig)

    return plot