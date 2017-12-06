import random
from time import sleep

RATING_RANGE = 100
MAX_RAND_PROB = 0.3
MAX_TIE_PROB = 0.2

class Game(object):

    # return 0 if agent0 wins, 1 if agent1 wins and None in case of a tie.
    def play(self, agent0, agent1):
        sleep(1) # emulate an unresponsive task

        if random.random() < 0.1: # emulate errors with low probability
            raise Exception

        if random.random() < 0.01: # return some non-valid values
            return random.choice(["", -10, 0.5, {}])

        res = int(agent0.r - agent1.r < 0) # result of the match if it was deterministic

        if random.random() < MAX_RAND_PROB - float(abs(agent0.r - agent1.r)) / RATING_RANGE: # add some randomness
            if random.random() < MAX_TIE_PROB - float(abs(agent0.r - agent1.r)) / RATING_RANGE : # when players have close level, return tie game with a certain probability
                return None
            return 1 - res
        else:
            return res


class Agent(object):

    def __init__(self):
        self.r = random.randint(0, RATING_RANGE -1)
