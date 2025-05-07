import random
import json


def get_keyframes(i):

    min_time = 90
    max_time = 730
    current_state = 0
    p_change = 0.5
    interval = 30

    keyframes = [{"pose": current_state, "time": 0.0}]

    for t in range(min_time, max_time, interval):

        # sample the distribution to determine if we change the current state
        value = random.random()

        if value <= p_change:
            current_state = 1.7 if current_state == 0 else 0
            keyframes.append(
                {"pose": current_state, "time": t + int(random.random() * 10)}
            )

    return keyframes


if __name__ == "__main__":

    for i in range(11):
        with open("output/keyframes_door_{i}.json".format(i=i), "w") as output:
            output.write(json.dumps({"keyframes": get_keyframes(i)}, indent=4))
