import random

from fpm.utils import get_output_path, save_file


def generate_door_keyframes(start_frame, end_frame, **kwargs):

    current_state = kwargs.get("start_state")
    interval = kwargs.get("sampling_interval")
    p_change = kwargs.get("state_change_probability")

    keyframes = [{"pose": current_state, "time": 0.0}]

    for t in range(start_frame, end_frame, interval):
        # TODO Simplify the sampling of states and timestamps
        current_state = sample_door_state_open_close(p_change, current_state)
        time_delta = sample_time_delta()
        keyframes.append({"pose": current_state, "time": t + time_delta})

    return keyframes


def sample_time_delta():
    # TODO Why are timestamps integers?
    return int(random.random() * 10)


def sample_door_state_open_close(
    p_change, current_state, open_angle=1.7, closed_angle=0.0
):
    # sample the distribution to determine if we change the current state
    value = random.random()
    if value <= p_change:
        if current_state == closed_angle:
            state = open_angle
        else:
            state = closed_angle
    else:
        state = current_state

    return state


def get_keyframes(base_path, **kwargs):
    output_path = get_output_path(base_path, "doors/behaviours/keyframes")
    num_doors = kwargs.get("num_doors", 11)
    for i in range(num_doors):
        keyframes = generate_door_keyframes(**kwargs)
        file_name = "keyframes_door_{}.json".format(i)
        contents = {"keyframes": keyframes}
        save_file(output_path, file_name, contents)
