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
docstring
"""
# Futures
from __future__ import absolute_import

# Built-in modules
import random

# Own modules
import microprobe.code
import microprobe.passes.address
import microprobe.passes.branch
import microprobe.passes.decimal
import microprobe.passes.float
import microprobe.passes.initialization
import microprobe.passes.instruction
import microprobe.passes.memory
import microprobe.passes.register
import microprobe.passes.structure
import microprobe.passes.symbol
from microprobe.exceptions import MicroprobePolicyError
from microprobe.utils.logger import get_logger
from microprobe.utils.misc import RNDINT

__author__ = "Ramon Bertran"
__copyright__ = "Copyright 2011-2021 IBM Corporation"
__credits__ = []
__license__ = "IBM (c) 2011-2021 All rights reserved"
__version__ = "0.5"
__maintainer__ = "Ramon Bertran"
__email__ = "rbertra@us.ibm.com"
__status__ = "Development"  # "Prototype", "Development", or "Production"

# Constants
LOG = get_logger(__name__)
__all__ = ["NAME", "DESCRIPTION", "SUPPORTED_TARGETS", "policy"]

NAME = "epi"
DESCRIPTION = "epi generation policy"
SUPPORTED_TARGETS = ["power_v207-power8-ppc64_linux_gcc"]


# Functions
def policy(target, wrapper, **kwargs):
    """
    Benchmark generation policy.

    A benchmark generation policy. Given a *target* and a *synthesizeresizer*
    object, this functions adds a predefined set of transformation passes to
    generate microbenchmarks with certain characteristics.

    Extra arguments can be passed to the policy via *kwargs* in order to
    modify the default behavior.

    :param target: Target object
    :type target: :class:`Target`
    :param wrapper: wrapper object
    :type wrapper: :class:`wrapper`
    """

    if target.name not in SUPPORTED_TARGETS:
        raise MicroprobePolicyError(
            "Policy '%s' not valid for target '%s'. Supported targets are:"
            " %s" % (NAME, target.name, ",".join(SUPPORTED_TARGETS)))

    instr = kwargs['instruction']
    sequence = [kwargs['instruction']]

    instruction = microprobe.code.ins.Instruction()
    instruction.set_arch_type(instr)
    # context = microprobe.code.context.Context()

    floating = False
    vector = False
    for operand in instruction.operands():
        if operand.type.immediate:
            continue

        if operand.type.float:
            floating = True

        if operand.type.vector:
            vector = True

    synthesizer = microprobe.code.Synthesizer(target,
                                              wrapper,
                                              value=0b01010101)

    rand = random.Random()
    rand.seed(13)

    synthesizer.add_pass(
        microprobe.passes.initialization.InitializeRegistersPass(
            value=RNDINT()))

    if vector and floating:
        synthesizer.add_pass(
            microprobe.passes.initialization.InitializeRegistersPass(
                v_value=(1.000000000000001, 64)))
    elif vector:
        synthesizer.add_pass(
            microprobe.passes.initialization.InitializeRegistersPass(
                v_value=(RNDINT(), 64)))
    elif floating:
        synthesizer.add_pass(
            microprobe.passes.initialization.InitializeRegistersPass(
                fp_value=1.000000000000001))

    synthesizer.add_pass(
        microprobe.passes.structure.SimpleBuildingBlockPass(
            kwargs['benchmark_size']))

    synthesizer.add_pass(
        microprobe.passes.instruction.SetInstructionTypeBySequencePass(
            sequence))

    if instr.mnemonic in ['LSWX', 'STSWX']:
        synthesizer.add_pass(
            microprobe.passes.initialization.InitializeRegisterPass(
                "XER", 256, force_control=True))
        # context.set_register_value(target.registers["XER"], 256)

    synthesizer.add_pass(
        microprobe.passes.address.UpdateInstructionAddressesPass())

    synthesizer.add_pass(microprobe.passes.branch.BranchNextPass())

    if instr.mnemonic in ['LMW', 'LSWI']:
        synthesizer.add_pass(
            microprobe.passes.memory.SingleMemoryStreamPass(16, 256, length=8))
    else:
        synthesizer.add_pass(
            microprobe.passes.memory.SingleMemoryStreamPass(16, 256))

    synthesizer.add_pass(
        microprobe.passes.float.InitializeMemoryFloatPass(
            value=1.000000000000001))

    synthesizer.add_pass(
        microprobe.passes.decimal.InitializeMemoryDecimalPass(value=1))

    if kwargs['dependency_distance'] < 1:
        synthesizer.add_pass(
            microprobe.passes.register.NoHazardsAllocationPass())

    synthesizer.add_pass(
        microprobe.passes.register.DefaultRegisterAllocationPass(
            rand, dd=kwargs['dependency_distance']))

    synthesizer.add_pass(
        microprobe.passes.address.UpdateInstructionAddressesPass())

    if instr.disable_asm:
        synthesizer.add_pass(
            microprobe.passes.symbol.ResolveSymbolicReferencesPass(
                instructions=[instr]))

    if (not synthesizer.wrapper.context().symbolic
            or instr.mnemonic in ['BLA', 'BA', 'BCLA', 'BCA']):
        synthesizer.add_pass(
            microprobe.passes.symbol.ResolveSymbolicReferencesPass())

    return synthesizer
