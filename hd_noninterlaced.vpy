#!/usr/bin/env python

#VapourSynth script tuned for HD live-action video without interlacing.

import vapoursynth
import havsfunc

video = vapoursynth.core.ffms2.Source(source="{input_file}")

video = havsfunc.Deblock_QED(video)
video = havsfunc.MCTemporalDenoise(video, settings="very low")

video.set_output()
