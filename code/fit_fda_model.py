#!/usr/bin/env python

import sys
import argparse
import numpy as np

import itertools
import mir_eval
import cPickle as pickle

import FDA
import segmenter

def process_arguments():
    parser = argparse.ArgumentParser(description='OLDA fit for music segmentation')

    parser.add_argument(    'input_file',
                            action  =   'store',
                            help    =   'path to training data (from make_*_train.py)')

    parser.add_argument(    'output_file',
                            action  =   'store',
                            help    =   'path to save model file')

    return vars(parser.parse_args(sys.argv[1:]))

def load_data(input_file):

    with open(input_file, 'r') as f:
        #   X = features
        #   Y = segment boundaries (as beat numbers)
        #   B = beat timings
        #   T = true segment boundaries (seconds)
        #   F = filename

        X, Y, B, T, F = pickle.load(f)

    return X, Y, B, T, F

def score_model(model, x, b, t):

    # First, transform the data
    if model is not None:
        xt = model.dot(x)
    else:
        xt = x

    # Then, run the segmenter
    boundary_beats = segmenter.get_segments(xt)

    boundary_times = mir_eval.util.adjust_segment_boundaries(b[boundary_beats], 
                                                             t_min=0.0,
                                                             t_max=t[-1])

    score = mir_eval.segment.frame_clustering_nce(t, boundary_times)[-1]

    return score

def make_train(X, Y):

    X_train = []
    Y_train = []

    label   = 0

    for (i, (Xi, Yi)) in enumerate(itertools.izip(X, Y)):
        for seg_start, seg_end in zip(Yi[:-1], Yi[1:]):
            X_train.extend(list(Xi.T[seg_start:seg_end]))
            Y_train.extend( (seg_end - seg_start) * [label])

            label = label + 1

    return np.array(X_train), np.array(Y_train, dtype=int)
    

def fit_model(X, Y, B, T):

    SIGMA = 10**np.arange(0, 8)

    best_score  = -np.inf
    best_sigma  = None
    model       = None

    X_train, Y_train = make_train(X, Y)
    for sig in SIGMA:
        O = FDA.FDA(alpha=sig)
        O.fit(X_train, Y_train)

        scores = [score_model(O.components_, *z) for z in zip(X, B, T)]

        mean_score = np.mean(scores)
        print 'Sigma=%.2e, score=%.3f' % (sig, mean_score)

        if mean_score > best_score:
            best_score  = mean_score
            best_sigma  = sig
            model       = O.components_

    print 'Best sigma: %.2e' % best_sigma
    return model

if __name__ == '__main__':
    parameters = process_arguments()

    X, Y, B, T, F = load_data(parameters['input_file'])

    model = fit_model(X, Y, B, T)

    np.save(parameters['output_file'], model)