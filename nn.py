import random
import collections

random.seed()

INPUT = 16
OUTPUT = 32
BRAINS = 200

CONNECTIONS = 5

def evolve(network, state): #returns new state 
    raw = {}
    for node, on in state.iteritems():
        if on:
            for target, strength in network[node]:
                if not new_s.has_key(target):
                    raw[target] = 0
                raw[target] += strength
    return dict((node, energy > 1) for node, energy in raw.iteritems())
    
def random_network():
    brains = int(random.expovariate(1.0 / BRAINS))
    total = INPUT + OUTPUT + BRAINS
    network = {}
    for i in range(INPUT + 1, total):
        con = int(random.expovariate(1.0 / CONNECTIONS))
        for j in range(1, con):
            strength = random.random() * 2.5 - 1
            source = random.randint(1, total)
            if not network.has_key(source): network[source] = []
            network[source].append((i, strength))
    return network
    
def sex(a, b):
    network = {}
    high_key = 0
    for key, values in a.iteritems():
        network[key] = values
        if key > high_key: high_key = key
    for key, values in b.iteriems():
        if key > high_key: high_key = key
        if network.has_key(key):
            network[key].extend(values)
        else:
            network[key] = value
    for key, values in network.iteritems():
        new_values = []
        for v in values:
            if random.choice([True, False]):
                new_values.append(v + random.normalvariate(0, 0.1))
        network[key] = new_values
    add = int(random.expovariate(1.0 / (BRAINS / 10)))
    for i in range(0, add):
        src = random.randint(1, high_key)
        target = random.randint(1, high_key + (BRAINS / 10 ))
        strength = random.random() * 2.5 - 1
        if not network.has_key(src): network[src] = []
        network[src].append((target, strength))
    return network
    
def trial(networks, input_generator, output_scorer): #returns an array of scores w/ index matching network index
    init = input_generator()
    iters = 0
    old_best = 0
    new_best = 0
    states = [init] * len(networks)
    while new_best > old_best or iters < 100:
        old_best = new_best
        new_best = 0
        iters += 1
        for i in range(0, len(networks)):
            states[i] = evolve(networks[i], states[i])
            s = output_scorer(init, states[i])
            if s > new_best: new_best = s
    return [output_scorer(init, states[i]) for i in range(0, len(networks))]
    

