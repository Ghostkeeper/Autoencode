#!/usr/bin/env python

#VapourSynth script tuned for DVD live-action video with bottom-field-first interlacing.

import vapoursynth
import havsfunc

video = vapoursynth.core.ffms2.Source(source="{input_file}")

video = havsfunc.QTGMC(video, TFF=False)
video = havsfunc.Deblock_QED(video)
video = havsfunc.MCTemporalDenoise(video, settings="very low")

video.set_output()
