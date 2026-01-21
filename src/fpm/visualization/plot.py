import matplotlib.pyplot as plt
from matplotlib.axes import Axes
import numpy as np

# colors = ("#FF6666", "#005533", "#1199EE")  # Colorblind-safe RGB
colors = ("#D55E00", "#009E73", "#56B4E9")  # Using a different colorblind-safe palette


def plot_3d_frame(ax, matrix, name=None):
    """Plot a frame in 3D
    Adapted from: https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.transform.Rotation.html
    """
    loc = np.array([matrix[:3, 3], matrix[:3, 3]])
    for i, (axis, c) in enumerate(zip((ax.xaxis, ax.yaxis, ax.zaxis), colors)):
        axlabel = axis.axis_name
        axis.set_label_text(axlabel)
        axis.label.set_color(c)
        axis.line.set_color(c)
        axis.set_tick_params(colors=c)
        line = np.zeros((2, 3))
        line[1, i] = matrix[3, 3]
        line_rot = np.zeros((2, 3))
        line_rot[0] = np.dot(matrix[:3, :3], line[0, :])
        line_rot[1] = np.dot(matrix[:3, :3], line[1, :])
        line_plot = line_rot + loc
        ax.plot(line_plot[:, 0], line_plot[:, 1], line_plot[:, 2], c)
        text_loc = line[1] * 1.2
        text_loc_rot = np.dot(matrix[:3, :3], text_loc)
        text_plot = text_loc_rot + loc[0]
        ax.text(*text_plot, axlabel.upper(), color=c, va="center", ha="center")
    ax.text(
        *matrix[:3, 3],
        name,
        color="k",
        va="center",
        ha="center",
        # fontsize=5 * matrix[3, 3] * 2,
    )


def plot_2d_robot(ax, matrix, width, length):
    x_vector = get_vector_x_axis(matrix)
    x_vector = x_vector / np.linalg.norm(x_vector)
    if np.dot(x_vector, np.array([1.0, 0.0, 0.0])) == 0.0:
        angle = 0.0
    else:
        angle = 90.0

    x = matrix[0, 3] - (width / 2)
    y = matrix[1, 3] - (length / 2)
    ax.add_patch(
        plt.Rectangle(
            (x, y),
            width,
            length,
            rotation_point="center",
            angle=angle,
            alpha=0.25,
            fc="grey",
            edgecolor="black",
        )
    )


def get_vector_x_axis(matrix):
    loc = np.array([matrix[:3, 3], matrix[:3, 3]])
    line = np.zeros((2, 3))
    line[1, 0] = matrix[3, 3]
    line_rot = np.zeros((2, 3))
    line_rot[0] = np.dot(matrix[:3, :3], line[0, :])
    line_rot[1] = np.dot(matrix[:3, :3], line[1, :])
    line_plot = line_rot + loc
    return line_plot[1, :] - line_plot[0, :]


def plot_2d_frame(ax: Axes, matrix, name=None, label_axis=False):
    loc = np.array([matrix[:3, 3], matrix[:3, 3]])
    for i, (axis_label, c) in enumerate(zip(("x", "y", "z"), colors)):
        line = np.zeros((2, 3))
        line[1, i] = matrix[3, 3]
        line_rot = np.zeros((2, 3))
        line_rot[0] = np.dot(matrix[:3, :3], line[0, :])
        line_rot[1] = np.dot(matrix[:3, :3], line[1, :])
        line_plot = line_rot + loc
        ax.plot(line_plot[:, 0], line_plot[:, 1], c)
        text_loc = line[1] * 1.5
        text_loc_rot = np.dot(matrix[:3, :3], text_loc)
        text_plot = text_loc_rot + loc[0]
        if label_axis:
            ax.text(
                text_plot[0],
                text_plot[1],
                axis_label,
                color=c,
                va="center",
                ha="center",
                fontsize="xx-small",
            )
    ax.text(
        matrix[0, 3],
        matrix[1, 3],
        name,
        color="k",
        va="bottom",
        ha="center",
        fontsize="xx-small",
        # fontsize=5 * matrix[3, 3] * 2,
    )


if __name__ == "__main__":

    m1 = np.array(
        [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
    )
    m2 = np.array(
        [
            [0.0, 1.0, 0.0, 3.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    m3 = np.array(
        [
            [1.0, 0.0, 0.0, 6.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    m4 = np.array(
        [
            [0.0, 0.0, 1.0, 9.0],
            [0.0, 1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    ax = plt.figure().add_subplot(projection="3d", proj_type="ortho")
    plot_3d_frame(ax, m1, "placement-1234")
    plot_3d_frame(ax, m2, "placement-5678")

    ax.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    plt.show()

    ax = plt.figure().add_subplot()
    plot_2d_frame(ax, m1, "placement-1234")
    plot_2d_frame(ax, m2, "placement-5678")
    plot_2d_frame(ax, m3, "placement-9")
    plot_2d_frame(ax, m4, "placement-10")
    ax.set_aspect("equal", adjustable="box")
    plt.tight_layout()
    plt.show()
