#!/usr/bin/env python

#VapourSynth script tuned for HD anime files.

import vapoursynth

video = vapoursynth.core.ffms2.Source(source="{input_file}")
#TODO: For now this is a completely transparent frame serving.
video.set_output()
