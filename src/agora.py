#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# AGORA v3.1
# python 3.5
# Copyright © 2006-2022 IBENS/Dyogen, 2020-2021 EMBL-European Bioinformatics Institute, 2021-2022 Genome Research Ltd : Matthieu MUFFATO, Alexandra LOUIS, Thi Thuy Nga NGUYEN, Hugues ROEST CROLLIUS
# mail : agora@bio.ens.psl.eu
# This is free software; you may copy, modify and/or distribute this work under the terms of the GNU General Public License, version 3 or later and the CeCiLL v2 license in France

import multiprocessing
import os
import re
import sys

import utils.myAgoraWorkflow
import utils.myFile
import utils.myPhylTree
import utils.myTools
from utils.myTools import file

__doc__ = """
    Run all the AGORA programs according to configuration file

    Usage:
          src/agora.py conf/agora-basic.ini
          src/agora.py conf/agora-basic.ini -workingDir=example/results -nbThreads=4
"""

arguments = utils.myTools.checkArgs(
    [("agora.ini", file)],
    [("workingDir", str, "."), ("nbThreads", int, multiprocessing.cpu_count()), ("forceRerun", bool, False), ("sequential", bool, True), ("printWorkflowGraph", str, ""),
     ],
    __doc__)

# loading configuration file
################################
bysections = {}
f = utils.myFile.openFile(arguments["agora.ini"], "r")
for l in f:

    l = l.partition("#")[0].strip()
    if l.startswith(">"):
        curr = []
        bysections[l[1:].strip().lower()] = curr
    elif len(l) > 1:
        curr.append(l)
f.close()


# Cut a string for delim
##########################
def partition(s, delim):
    x = s.partition(delim)
    return (x[0].strip(), x[2].strip())


# Files and directory section
##############################
conffiles = {}
for x in bysections["files"]:
    x = partition(x, "=")
    conffiles[x[0].lower()] = x[1]

# All input paths are relative to the directory of the configuration file
files = {}
inputDir = os.path.dirname(arguments["agora.ini"])
for f in ["speciesTree", "genes"]:
    files[f] = os.path.normpath(os.path.join(inputDir, conffiles[f.lower()]))
if 'geneTrees'.lower() in conffiles:
    files["geneTrees|orthologyGroups"] = os.path.normpath(os.path.join(inputDir, conffiles['geneTrees'.lower()]))
else:
    files["geneTrees|orthologyGroups"] = os.path.normpath(os.path.join(inputDir, conffiles['orthologyGroups'.lower()]))
outputDir = arguments["workingDir"]
for (f, s) in utils.myAgoraWorkflow.AgoraWorkflow.defaultPaths.items():
    files[f] = os.path.normpath(os.path.join(outputDir, conffiles.get(f.lower(), s)))
scriptDir = os.path.dirname(os.path.abspath(__file__))

phylTree = utils.myPhylTree.PhylogeneticTree(files["speciesTree"])


# TODO: add options in config file to change the target ancestors / species
workflow = utils.myAgoraWorkflow.AgoraWorkflow(phylTree.root, None, scriptDir, files)

# Ancestral genes lists Section
################################


# all ancGenes task - gather nickname and only launch if explicitly requested to (backwards compatibility)
allname = workflow.allAncGenesName
patternall = re.compile(r'=.*\ball\b')
for x in bysections["ancgenes"]:
    if patternall.search(x):
        x = partition(x, "=")
        allname = x[0].strip()

workflow.addAncGenesGenerationAnalysis()

ancGenes = {allname: workflow.allAncGenesName, "0": workflow.allAncGenesName}

# Parse the section
for x in bysections["ancgenes"]:
    if patternall.search(x):
        continue
    x = partition(x, "=")
    (params, root) = partition(x[1], "!")
    # index
    t = x[0].split(",")
    sizes = params.split(",")
    assert len(t) == len(sizes)
    minSizes = []
    maxSizes = []
    dirnameTemplate = "size-%s-%s"
    ancGenesDirNames = []
    for i in range(len(sizes)):
        size = sizes[i].split()
        minSizes.append(size[0])
        maxSizes.append(size[1])
        dirname = dirnameTemplate % tuple(size)
        ancGenes[t[i]] = dirname
        ancGenesDirNames.append(dirname)
    minSizesStr = ",".join(minSizes)
    maxSizesStr = ",".join(maxSizes)

    workflow.addAncGenesFilterAnalysis("size", [minSizesStr, maxSizesStr], root)

    if len(ancGenesDirNames) > 1:
        taskname = dirnameTemplate % (minSizesStr, maxSizesStr)
        for dirname in ancGenesDirNames:
            workflow.addDummy(("ancgenes", dirname), [("ancgenes", taskname)])

# Pairwise comparison section
#############################


for x in bysections.get("pairwise", []):
    x = partition(x, "=")
    dirname = ancGenes[x[0].strip()]
    (params, root) = partition(x[1], "!")
    params = params.split()

    # Pairwise comparison tasks
    workflow.addPairwiseAnalysis(dirname, params[0], params[1:], root)

# Integration section
#####################
for x in bysections.get("integration", []):

    (params, root) = partition(x, "!")
    (params, input) = partition(params, "<")
    (params, output) = partition(params, ">")
    params = params.split()

    currMethod = None
    # method's name
    if params[0].startswith("["):
        currMethod = params.pop(0)[1:-1]

    # used compared pairs
    dirname = None
    if params[-1].startswith("("):
        dirname = ancGenes[params.pop()[1:-1]]

    workflow.addIntegrationAnalysis(params[0], params[1:], dirname, currMethod, input, output, root)

# Print the workflow and exit
if arguments["printWorkflowGraph"]:
    fh = utils.myFile.openFile(arguments["printWorkflowGraph"], "w")
    workflow.tasklist.printGraphviz(fh)
    fh.close()
    sys.exit(0)

# Launching tasks in multiple threads
#####################################
failed = workflow.tasklist.runAll(arguments["nbThreads"], arguments["sequential"], arguments["forceRerun"])
sys.exit(failed)
