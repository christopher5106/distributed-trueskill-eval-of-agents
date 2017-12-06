# With a Game and a list of Agents given in game.py file,
# the goal is to play num_matches random games between the
# agents and produce a trueskill rating of the agents.

DEBUG = False

import os
import random
import argparse
from time import sleep
from timeit import default_timer
from game import Game, Agent
from trueskill import Rating, quality_1vs1, rate_1vs1
from dask.distributed import Client

def get_nodes(ip_file):
    nodes = []
    with open(ip_file, "rt") as f_original:
        for line in f_original:
                nodes.append(line.strip())
    return nodes

def update_ratings(match, ratings):
    result, i1, i2 = match.result()
    if DEBUG:
        r1, r2 = ratings[i1].mu, ratings[i2].mu

    if result == 0:
        winner = i1
        loser = i2
    else:
        winner = i2
        loser = i1

    ratings[winner], ratings[loser] = rate_1vs1(ratings[winner], ratings[loser], drawn=(result == None))  # update the ratings after the match

    if DEBUG:
        print("Match result: {}".format(result))
        new_r1, new_r2 = ratings[i1].mu, ratings[i2].mu
        print(new_r1, new_r2)
        if i1 != i2:
            if result == 0:
                assert ((new_r1 > r1) and (new_r2 < r2)), \
                    "rating updates for 1: {} and 2: {}".format( (new_r1 > r1),  (new_r2 < r2))

            if (result ==1):
                assert ((new_r1 < r1) and (new_r2 > r2)), \
                    "rating updates for 1: {} and 2: {}".format( (new_r1 < r1),  (new_r2 > r2))

            # if result == None:
            #     assert (int(max(new_r1, new_r2)* 10**5) <= int(max(r1, r2) * 10**5)) \
            #         and (int(min(new_r1, new_r2)* 10**5) >= int(min(r1, r2) * 10**5)), \
            #         "rating updates for 1: {} -> {} and 2: {} -> {}".format( r1, new_r1, r2, new_r2 )
    return


def compute_ratings(matches, ratings):
    for match in matches:
        if valid_result(match):
            update_ratings(match, ratings)


def estimate_accuracy(agents, ratings):
    accuracy = 0
    for i in range(len(agents)):
        for j in range(len(agents)):
            if (agents[i].r - agents[j].r) * (ratings[i].mu - ratings[j].mu ) >= 0:
                accuracy += 1
    return float(accuracy) / len(agents) / len(agents)


def game_setup(num_agents):
    game = Game()
    agents = [Agent() for i in range(num_agents)]
    ratings = [Rating() for i in range(num_agents)]
    return game, agents, ratings


def play(game, agents):
    i1 = random.randint(0, len(agents) - 1)
    i2 = random.randint(0, len(agents) - 2) # I prefer to avoid matches against self
    if i2 >= i1:
        i2 = i2 + 1
    return (game.play( agents[i1], agents[i2] ), i1, i2)


def run_games(game, agents, num_matches, client):
    jobs = []
    for _ in range(num_matches):
        jobs.append(client.submit(play, game, agents)) #,resources={'GPU': 1}
    return jobs


def valid_result(job):
    return ((job.status == "finished") and (job.result()[0] in [0,1,None]))


def check_status(jobs):
    while True:
        pending = 0
        error = 0
        completed = 0
        for job in jobs:
            if job.status == "pending":
                pending += 1
            elif valid_result(job):
                completed += 1
            else:
                error += 1

        print("{}/{} - Pending: {}, Error: {}, Completed: {}, Elapsed time: {:.2f}" \
            .format(completed + error, len(jobs), pending, error, completed, default_timer() - start), end="\r")
        sleep(1)
        if completed + error == len(jobs):
            print("")
            return


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--num-agents', type=int, default=10,
                        help="number of players")
    parser.add_argument('--num-matches', type=int, default=100,
                        help="number of game matches to play")
    parser.add_argument('--ip-file', type=str, default="ips.txt",
                        help="location of the nodes")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()

    # setup the game
    game, agents, ratings = game_setup(args.num_agents)

    # run the game matches on the cluster
    nodes = get_nodes(args.ip_file)
    print("Connecting to cluster scheduler {} with workers:".format(nodes[0]))
    client = Client(nodes[0] + ':8786')
    for worker, cores in client.ncores().items():
        print("{:>35} {} cores".format(worker, cores))
    client.upload_file('game.py')

    start = default_timer()
    matches = run_games(game, agents, args.num_matches, client)
    check_status(matches)
    print("Game run in {:.2f}".format( default_timer() - start))

    # here we could do something with failed matches (errors)

    # run rating evaluations
    start = default_timer()
    compute_ratings(matches, ratings)
    print("Skills computed in {:.2f}".format( default_timer() - start))

    # compute approximate accuracy of ratings
    accuracy = estimate_accuracy(agents, ratings)
    print("Accuracy of the ratings: {:.2f}".format(accuracy))
