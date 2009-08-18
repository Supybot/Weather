###
# Copyright (c) 2005, James Vega
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
###

from supybot.test import *

class WeatherTestCase(PluginTestCase):
    plugins = ('Weather',)
    if network:
        def testHam(self):
            self.assertNotError('ham Columbus, OH')
            self.assertNotError('ham 43221')
            self.assertNotRegexp('ham Paris, FR', 'Virginia')
            self.assertError('ham alsdkfjasdl, asdlfkjsadlfkj')
            self.assertNotError('ham London, uk')
            self.assertNotError('ham London, UK')
            self.assertNotError('ham Munich, de')
            self.assertNotError('ham Tucson, AZ')
            # "Multiple locations found" test
            self.assertNotError('ham hell')
            self.assertNotError('ham sandwich')

        def testCnn(self):
            self.assertNotError('cnn Columbus, OH')
            self.assertNotError('cnn 43221')
            self.assertNotRegexp('cnn Paris, FR', 'Virginia')
            self.assertError('cnn alsdkfjasdl, asdlfkjsadlfkj')
            self.assertNotError('cnn London, uk')
            self.assertNotError('cnn London, UK')
            self.assertNotError('cnn Munich, de')
            self.assertNotError('cnn Tucson, AZ')

        def testWunder(self):
            self.assertNotError('wunder Columbus, OH')
            self.assertNotError('wunder 43221')
            self.assertNotRegexp('wunder Paris, FR', 'Virginia')
            self.assertError('wunder alsdkfjasdl, asdlfkjsadlfkj')
            self.assertNotError('wunder London, england')
            self.assertNotError('wunder Munich, germany')
            self.assertNotError('wunder Tucson, AZ')

        def testTemperatureUnit(self):
            try:
                orig = conf.supybot.plugins.Weather.temperatureUnit()
                conf.supybot.plugins.Weather.temperatureUnit.setValue('F')
                self.assertRegexp('cnn Columbus, OH', r'is -?\d+.F')
                self.assertRegexp('ham Columbus, OH', r'is -?\d+.F')
                conf.supybot.plugins.Weather.temperatureUnit.setValue('C')
                self.assertRegexp('cnn Columbus, OH', r'is -?\d+.C')
                self.assertRegexp('ham Columbus, OH', r'is -?\d+.C')
                conf.supybot.plugins.Weather.temperatureUnit.setValue('K')
                self.assertRegexp('cnn Columbus, OH', r'is -?\d+ K')
                self.assertRegexp('ham Columbus, OH', r'is -?\d+ K')
            finally:
                conf.supybot.plugins.Weather.temperatureUnit.setValue(orig)

        def testNoEscapingWebError(self):
            self.assertNotRegexp('ham "buenos aires"', 'WebError')

        def testWeatherRepliesWithBogusLocation(self):
            self.assertRegexp('weather some place that doesn\'t exist', r'.')

        def testConvertConfig(self):
            try:
                convert = conf.supybot.plugins.Weather.convert()
                unit = conf.supybot.plugins.Weather.temperatureUnit()
                conf.supybot.plugins.Weather.convert.setValue(False)
                conf.supybot.plugins.Weather.temperatureUnit.setValue('C')
                self.assertRegexp('ham london, gb', r'-?\d+.C')
                self.assertRegexp('ham 02115', r'-?\d+.F')
                conf.supybot.plugins.Weather.temperatureUnit.setValue('F')
                self.assertRegexp('ham london, gb', r'-?\d+.C')
                self.assertRegexp('ham 02115', r'-?\d+.F')
                conf.supybot.plugins.Weather.convert.setValue(True)
                conf.supybot.plugins.Weather.temperatureUnit.setValue('C')
                self.assertRegexp('ham london, gb', r'-?\d+.C')
                self.assertRegexp('ham 02115', r'-?\d+.C')
                conf.supybot.plugins.Weather.temperatureUnit.setValue('F')
                self.assertRegexp('ham london, gb', r'-?\d+.F')
                self.assertRegexp('ham 02115', r'-?\d+.F')
            finally:
                conf.supybot.plugins.Weather.convert.setValue(convert)
                conf.supybot.plugins.Weather.temperatureUnit.setValue(unit)


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
