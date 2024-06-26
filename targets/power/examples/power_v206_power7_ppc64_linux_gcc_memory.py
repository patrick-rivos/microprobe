#!/usr/bin/env python
# Copyright 2011-2021 IBM Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
power_v206_power7_ppc64_linux_gcc_memory.py

Example python script to show how to generate microbenchmarks with particular
levels of activity in the memory hierarchy.
"""

# Futures
from __future__ import absolute_import

# Built-in modules
import multiprocessing as mp
import os
import random
import sys
from typing import List, Tuple

# Own modules
import microprobe.code
import microprobe.passes.address
import microprobe.passes.ilp
import microprobe.passes.initialization
import microprobe.passes.instruction
import microprobe.passes.memory
import microprobe.passes.register
import microprobe.passes.structure
from microprobe import MICROPROBE_RC
from microprobe.exceptions import MicroprobeTargetDefinitionError
from microprobe.model.memory import EndlessLoopDataMemoryModel
from microprobe.target import import_definition
from microprobe.target.isa.instruction import InstructionType
from microprobe.target.uarch.cache import SetAssociativeCache
from microprobe.utils.cmdline import print_error, print_info
from microprobe.utils.typeguard_decorator import typeguard_testsuite

__author__ = "Ramon Bertran"
__copyright__ = "Copyright 2011-2021 IBM Corporation"
__credits__ = []
__license__ = "IBM (c) 2011-2021 All rights reserved"
__version__ = "0.5"
__maintainer__ = "Ramon Bertran"
__email__ = "rbertra@us.ibm.com"
__status__ = "Development"  # "Prototype", "Development", or "Production"

# Get the target definition
try:
    TARGET = import_definition("power_v206-power7-ppc64_linux_gcc")
except MicroprobeTargetDefinitionError as exc:
    print_error("Unable to import target definition")
    print_error("Exception message: %s" % str(exc))
    exit(-1)

assert TARGET.microarchitecture is not None, \
    "Target must have a defined microarchitecture"

BASE_ELEMENT = [
    element for element in TARGET.microarchitecture.elements.values()
    if element.name == 'L1D'
][0]
CACHE_HIERARCHY: List[SetAssociativeCache] = \
    TARGET.microarchitecture.cache_hierarchy.get_data_hierarchy_from_element(
        BASE_ELEMENT)

# Benchmark size
BENCHMARK_SIZE = 8 * 1024

# Fill a list of the models to be generated

MEMORY_MODELS: List[Tuple[str, List[SetAssociativeCache], List[int]]] = []

#
# Due to performance issues (long exec. time) this
# model is disabled
#
# MEMORY_MODELS.append(
#    (
#        "ALL", CACHE_HIERARCHY, [
#            25, 25, 25, 25]))

MEMORY_MODELS.append(("L1", CACHE_HIERARCHY, [100, 0, 0, 0]))
MEMORY_MODELS.append(("L2", CACHE_HIERARCHY, [0, 100, 0, 0]))
MEMORY_MODELS.append(("L3", CACHE_HIERARCHY, [0, 0, 100, 0]))
MEMORY_MODELS.append(("L1L3", CACHE_HIERARCHY, [50, 0, 50, 0]))
MEMORY_MODELS.append(("L1L2", CACHE_HIERARCHY, [50, 50, 0, 0]))
MEMORY_MODELS.append(("L2L3", CACHE_HIERARCHY, [0, 50, 50, 0]))
MEMORY_MODELS.append(("CACHES", CACHE_HIERARCHY, [33, 33, 34, 0]))
MEMORY_MODELS.append(("MEM", CACHE_HIERARCHY, [0, 0, 0, 100]))

# Enable parallel generation
PARALLEL = False

DIRECTORY = None


@typeguard_testsuite
def main():
    """Main function. """
    # call the generate method for each model in the memory model list

    if PARALLEL:
        print_info("Start parallel execution...")
        pool = mp.Pool(processes=MICROPROBE_RC['cpus'])
        pool.map(generate, MEMORY_MODELS, 1)
    else:
        print_info("Start sequential execution...")
        list(map(generate, MEMORY_MODELS))

    exit(0)


@typeguard_testsuite
def generate(model: Tuple[str, List[SetAssociativeCache], List[int]]):
    """Benchmark generation policy function. """

    assert DIRECTORY is not None, "DIRECTORY variable cannot be None"

    print_info(f"Creating memory model '{model[0]}' ...")
    memmodel = EndlessLoopDataMemoryModel(*model)

    modelname = memmodel.name

    print_info(f"Generating Benchmark mem-{modelname} ...")

    # Get the architecture
    garch = TARGET

    # For all the supported instructions, get the memory operations,
    sequence: List[InstructionType] = []
    for instr_name in sorted(garch.isa.instructions.keys()):

        instr = garch.isa.instructions[instr_name]

        if not instr.access_storage:
            continue
        if instr.privileged:  # Skip privileged
            continue
        if instr.hypervisor:  # Skip hypervisor
            continue
        if instr.trap:  # Skip traps
            continue
        if "String" in instr.description:  # Skip unsupported string instr.
            continue
        if "Multiple" in instr.description:  # Skip unsupported mult. ld/sts
            continue
        if instr.category in ['LMA', 'LMV', 'DS', 'EC',
                              'WT']:  # Skip unsupported categories
            continue
        if instr.access_storage_with_update:  # Not supported by mem. model
            continue
        if "Reserve Indexed" in instr.description:  # Skip (illegal intr.)
            continue
        if "Conditional Indexed" in instr.description:  # Skip (illegal intr.)
            continue
        if instr.name in ['LD_V1', 'LWZ_V1', 'STW_V1']:
            continue

        sequence.append(instr)

    # Get the loop wrapper. In this case we take the 'CInfPpc', which
    # generates an infinite loop in C using PowerPC embedded assembly.
    cwrapper = microprobe.code.get_wrapper("CInfPpc")

    # Define function to return random numbers (used afterwards)
    def rnd():
        """Return a random value. """
        return random.randrange(0, (1 << 64) - 1)

    # Create the benchmark synthesizer
    synth = microprobe.code.Synthesizer(garch, cwrapper())

    rand = random.Random()
    rand.seed(13)

    ##########################################################################
    # Add the passes we want to apply to synthesize benchmarks               #
    ##########################################################################

    # --> Init registers to random values
    synth.add_pass(
        microprobe.passes.initialization.InitializeRegistersPass(value=rnd))

    # --> Add a single basic block of size 'size'
    if memmodel.name in ['MEM']:
        synth.add_pass(
            microprobe.passes.structure.SimpleBuildingBlockPass(
                BENCHMARK_SIZE * 4))
    else:
        synth.add_pass(
            microprobe.passes.structure.SimpleBuildingBlockPass(
                BENCHMARK_SIZE))

    # --> Fill the basic block using the sequence of instructions provided
    synth.add_pass(
        microprobe.passes.instruction.SetInstructionTypeBySequencePass(
            sequence))

    # --> Set the memory operations parameters to fulfill the given model
    synth.add_pass(microprobe.passes.memory.GenericMemoryModelPass(memmodel))

    # --> Set the dependency distance and the default allocation. Sets the
    # remaining undefined instruction operands (register allocation,...)
    synth.add_pass(microprobe.passes.register.NoHazardsAllocationPass())
    synth.add_pass(
        microprobe.passes.register.DefaultRegisterAllocationPass(rand, dd=0))

    # Generate the benchmark (applies the passes).
    bench = synth.synthesize()

    print_info(f"Benchmark mem-{modelname} saving to disk...")

    # Save the benchmark
    synth.save(f"{DIRECTORY}/mem-{modelname}", bench=bench)

    print_info(f"Benchmark mem-{modelname} generated")
    return True


if __name__ == '__main__':
    # run main if executed from the command line
    # and the main method exists

    if len(sys.argv) != 2:
        print_info("Usage:")
        print_info("%s output_dir" % (sys.argv[0]))
        exit(-1)

    DIRECTORY = sys.argv[1]

    if not os.path.isdir(DIRECTORY):
        print_error(f"Output directory '{DIRECTORY}' does not exists")
        exit(-1)

    main()
