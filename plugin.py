###
# Copyright (c) 2005,2009, James Vega
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

import re

# Specifically use our local copy since later versions changed their interface
# and (depending on the version) don't work as well
from local import BeautifulSoup

import supybot.conf as conf
import supybot.utils as utils
from supybot.commands import *
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

try:
    feedparser = utils.python.universalImport('feedparser', 'local.feedparser')
except ImportError:
    raise callbacks.Error, \
            'You need the feedparser module installed to use this plugin.  ' \
            'Download the module at <http://www.feedparser.org/>.'

simplejson = None

try:
    import json as simplejson
except ImportError:
    pass

try:
    # The 3rd party simplejson module was included in Python 2.6 and renamed to
    # json.  Unfortunately, this conflicts with the 3rd party json module.
    # Luckily, the 3rd party json module has a different interface so we test
    # to make sure we aren't using it.
    if simplejson is None or hasattr(simplejson, 'read'):
        simplejson = utils.python.universalImport('simplejson',
                                                  'local.simplejson')
except ImportError:
    raise callbacks.Error, \
            'You need Python2.6 or the simplejson module installed to use ' \
            'this plugin.  Download the module at ' \
            '<http://undefined.org/python/#simplejson>.'

unitAbbrevs = utils.abbrev(['Fahrenheit', 'Celsius', 'Centigrade', 'Kelvin'])
unitAbbrevs['C'] = 'Celsius'
unitAbbrevs['Ce'] = 'Celsius'

noLocationError = 'No such location could be found.'
class NoLocation(callbacks.Error):
    pass

class Weather(callbacks.Plugin):
    weatherCommands = ('wunder', 'wunder rss', 'cnn', 'ham')
    threaded = True
    def callCommand(self, method, irc, msg, *args, **kwargs):
        try:
            super(Weather, self).callCommand(method, irc, msg, *args, **kwargs)
        except utils.web.Error, e:
            irc.error(str(e))

    def _noLocation():
        raise NoLocation, noLocationError
    _noLocation = staticmethod(_noLocation)

    def weather(self, irc, msg, args, location):
        """<US zip code | US/Canada city, state | Foreign city, country>

        Returns the approximate weather conditions for a given city.
        """
        channel = None
        if irc.isChannel(msg.args[0]):
            channel = msg.args[0]
        if not location:
            location = self.userValue('lastLocation', msg.prefix)
        if not location:
            raise callbacks.ArgumentError
        self.setUserValue('lastLocation', msg.prefix,
                          location, ignoreNoUser=True)
        args = [location]
        commandName = self.registryValue('command', channel)
        firstCommand = commandName
        command = self.getCommandMethod(commandName.split())
        try:
            command(irc, msg, args[:])
        except (NoLocation, utils.web.Error):
            self.log.info('%s lookup failed, Trying others.', firstCommand)
            for commandName in self.weatherCommands:
                if commandName != firstCommand:
                    self.log.info('Trying %s.', commandName)
                    try:
                        command = self.getCommandMethod(commandName.split())
                        command(irc, msg, args[:])
                        self.log.info('%s lookup succeeded.', commandName)
                        return
                    except NoLocation:
                        self.log.info('%s lookup failed as backup.',
                                      commandName)
            irc.error(format('Could not retrieve weather for %q.', location))
    weather = wrap(weather, [additional('text')])

    def _toCelsius(temp, unit):
        if unit == 'K':
            return temp - 273.15
        elif unit == 'F':
            return (temp - 32) * 5 /9
        else:
            return temp
    _toCelsius = staticmethod(_toCelsius)

    _temp = re.compile(r'(-?\d+)(.*?)(F|C)')
    def _getTemp(temp, deg, unit, chan):
        assert unit == unit.upper()
        assert temp == float(temp)
        default = conf.get(conf.supybot.plugins.Weather.temperatureUnit, chan)
        convert = conf.get(conf.supybot.plugins.Weather.convert, chan)
        # Short circuit if we're the same unit as the default or no conversion
        # has been requested
        if unitAbbrevs[unit] == default or not convert:
            return format('%0.1f%s%s', temp, deg, unit)
        temp = Weather._toCelsius(temp, unit)
        unit = 'C'
        if default == 'Kelvin':
            temp = temp + 273.15
            unit = 'K'
            deg = ' '
        elif default == 'Fahrenheit':
            temp = temp * 9 / 5 + 32
            unit = 'F'
        return '%0.1f%s%s' % (temp, deg, unit)
    _getTemp = staticmethod(_getTemp)

    _hamLoc = re.compile(
        r'<span class="Place">([^,]+), ([^,\n]+),(.*?)</span>', re.I)
    _interregex = re.compile(
        r'<span class="Place">([^,]+), ([^,\n]+?)</span>', re.I)
    _hamCond = re.compile(
        r'<td width="100%" colspan="2" align="center" class="Wx">([^<]+)</td>',
        re.I)
    _hamTemp = re.compile(
        r'<td valign="top" align="right" class="Temp">(-?\d+)(.*?)(F|C)</td>',
        re.I)
    _hamChill = re.compile(
        r'Wind Chill:</td>\s+<td align="right" class="Value">([^N][^<]+)</td>',
        re.I | re.S)
    _hamHeat = re.compile(
        r'Heat Index:</td>\s+<td align="right" class="Value">([^N][^<]+)</td>',
        re.I | re.S)
    _hamMultiLoc = re.compile(
        r'Select from one of[^<]+</b></font></td></tr>\s*<tr><td><font[^>]+>'
        r'\s*<a href="(/cgi-bin/hw3[^"]+)">', re.I | re.S)
    def ham(self, irc, msg, args, loc):
        """<US zip code | US/Canada city, state | Foreign city, country>

        Returns the approximate weather conditions for a given city.
        """
        url = 'http://www.hamweather.net/cgi-bin/hw3/hw3.cgi?' \
              'config=&forecast=zandh&pands=%s&Submit=GO' % \
              utils.web.urlquote(loc.lower())
        html = utils.web.getUrl(url)
        if 'was not found' in html:
            self._noLocation()

        # ham seems to automatically return a location for duplicate names with
        # no list of other possibilities anymore, so this code may not be
        # needed
        if 'Multiple Locations for' in html:
            m = self._hamMultiLoc.search(html)
            if m:
                url = 'http://www.hamweather.net/%s' % m.group(1)
                html = utils.web.getUrl(url)
            else:
                self._noLocation()
        headData = self._hamLoc.search(html)
        if headData is not None:
            (city, state, country) = headData.groups()
        else:
            headData = self._interregex.search(html)
            if headData:
                (city, state) = headData.groups()
            else:
                self._noLocation()
        city = utils.web.htmlToText(city.strip())
        state = utils.web.htmlToText(state.strip())
        temp = self._hamTemp.search(html)
        if temp is not None:
            (temp, deg, unit) = temp.groups()
            deg = utils.web.htmlToText(deg)
            temp = self._getTemp(float(temp), deg, unit, msg.args[0])
        conds = self._hamCond.search(html)
        if conds is not None:
            conds = conds.group(1)
        index = ''
        chill = self._hamChill.search(html)
        if chill is not None:
            chill = chill.group(1)
            chill = utils.web.htmlToText(chill)
            tempsplit = self._temp.search(chill)
            if tempsplit:
                (chill, deg, unit) = tempsplit.groups()
                chill = self._getTemp(float(chill), deg, unit,msg.args[0])
            if float(chill[:-2]) < float(temp[:-2]):
                index = format(' (Wind Chill: %s)', chill)
        heat = self._hamHeat.search(html)
        if heat is not None:
            heat = heat.group(1)
            heat = utils.web.htmlToText(heat)
            tempsplit = self._temp.search(heat)
            if tempsplit:
                (heat, deg, unit) = tempsplit.groups()
                heat= self._getTemp(float(heat), deg, unit,msg.args[0])
            if float(heat[:-2]) > float(temp[:-2]):
                index = format(' (Heat Index: %s)', heat)
        if temp and conds and city and state:
            conds = conds.replace('Tsra', 'Thunderstorms')
            conds = conds.replace('Ts', 'Thunderstorms')
            s = format('The current temperature in %s, %s is %s%s. '
                       'Conditions: %s.',
                       city, state, temp, index, conds)
            irc.reply(s.decode('latin1').encode('utf-8'))
        else:
            irc.errorPossibleBug('The format of the page was odd.')
    ham = wrap(ham, ['text'])

    _cnnSearchUrl = 'http://weather.cnn.com/weather/citySearch?' \
                    'search_term=%s&mode=json&filter=true'
    _cnnUrl='http://weather.cnn.com/weather/forecast.jsp?locCode=%s&zipCode=%s'
    _cnnFTemp = re.compile(r'<div class="cnnWeatherTempCurrent">' \
                           r'(-?\d+)(&deg;)</div>',
                           re.I | re.S)
    _cnnCond = re.compile(r'<span class="cnnWeatherConditionCurrent">' \
                          r'([^<]+)</span>',
                          re.I | re.S)
    _cnnHumid = re.compile(r'Humidity: </b>(\d+%)', re.I | re.S)
    _cnnWind = re.compile(r'Wind: </b>([^<\n\r]+)', re.I | re.S)
    # Certain countries are expected to use a standard abbreviation
    # The weather we pull uses weird codes.  Map obvious ones here.
    _cnnCountryMap = {'uk': 'en', 'de': 'ge'}
    def cnn(self, irc, msg, args, loc):
        """<US zip code | US/Canada city, state | Foreign city, country>

        Returns the approximate weather conditions for a given city.
        """
        if ' ' in loc:
            #If we received more than 1 argument, then we got a city with a
            #multi-word name.  ie ['Garden', 'City', 'KS'] instead of
            #['Liberal', 'KS'].
            loc = utils.str.rsplit(loc, None, 1)
            state = loc.pop().lower()
            city = ' '.join(loc)
            city = city.rstrip(',').lower()
            if state in self._cnnCountryMap:
                state = self._cnnCountryMap[state]
            loc = ' '.join([city, state])
        else:
            #We received a single argument.  Zipcode or station id.
            loc = loc.replace(',', '')
        url = self._cnnSearchUrl % (utils.web.urlquote(loc))
        json = simplejson.loads(utils.web.getUrl(url))
        if not json:
            self._noLocation()
        json = json[0]
        url = self._cnnUrl % (json['locCode'], json['zip'])
        text = utils.web.getUrl(url)
        location = ', '.join([json['city'], json['stateOrCountry']])
        temp = self._cnnFTemp.search(text)
        conds = self._cnnCond.search(text)
        humidity = self._cnnHumid.search(text)
        wind = self._cnnWind.search(text)
        if location and temp:
            (temp, deg) = temp.groups()
            unit = 'F'
            temp = self._getTemp(float(temp), deg, unit, msg.args[0])
            resp = [format('The current temperature in %s is %s.',
                           location, temp)]
            if conds is not None:
                resp.append(format('Conditions: %s.', conds.group(1)))
            if humidity is not None:
                resp.append(format('Humidity: %s.', humidity.group(1)))
            if wind is not None:
                resp.append(format('Wind: %s.', wind.group(1)))
            resp = map(utils.web.htmlToText, resp)
            irc.reply(' '.join(resp))
        else:
            irc.errorPossibleBug('Could not find weather information.')
    cnn = wrap(cnn, ['text'])

    class wunder(callbacks.Commands):
        _backupUrl = re.compile(r'<a href="(/global/stations[^"]+)">')

        _wunderUrl = 'http://mobile.wunderground.com/cgi-bin/' \
                     'findweather/getForecast?query='
        _wunderSevere = re.compile(r'font color="?#ff0000"?>([^<]+)<', re.I)
        _wunderMultiLoc = re.compile(r'<a href="([^"]+)', re.I | re.S)
        def wunder(self, irc, msg, args, loc):
            """<US zip code | US/Canada city, state | Foreign city, country>

            Returns the approximate weather conditions for a given city.
            """
            url = '%s%s' % (self._wunderUrl, utils.web.urlquote(loc))
            text = utils.web.getUrl(url)
            if 'Search not found' in text or \
               re.search(r'size="2"> Place </font>', text, re.I):
                Weather._noLocation()
            if 'Place: Temperature' in text:
                m = self._backupUrl.search(text)
                if m is not None:
                    url = 'http://mobile.wunderground.com' + m.group(1)
                    text = utils.web.getUrl(url)
            severe = ''
            m = self._wunderSevere.search(text)
            if m:
                severe = ircutils.bold(format('  %s', m.group(1)))
            text = self._formatSymbols(text)
            soup = BeautifulSoup.BeautifulSoup()
            soup.feed(text)
            # Get the table with all the weather info
            table = soup.first('table', {'border':'1'})
            if not table:
                Weather._noLocation()
            trs = table.fetch('tr')
            (time, location) = trs.pop(0).fetch('b')
            time = time.string
            location = location.string
            info = {}
            def isText(t):
                return not isinstance(t, BeautifulSoup.NavigableText) \
                       and t.contents
            def getText(t):
                s = t.string
                if s is BeautifulSoup.Null:
                    t = t.contents
                    num = t[0].string
                    units = t[1].string
                    # htmlToText strips leading whitespace, so we have to
                    # handle strings with &nbsp; differently.
                    if units.startswith('&nbsp;'):
                        units = utils.web.htmlToText(units)
                        s = ' '.join((num, units))
                    else:
                        units = utils.web.htmlToText(units)
                        s = ' '.join((num, units[0], units[1:]))
                return s
            for tr in trs:
                k = tr.td.string
                v = filter(isText, tr.fetch('td')[1].contents)
                value = map(getText, v)
                info[k] = ' '.join(value)
            temp = info['Temperature']
            if location and temp:
                (temp, deg, unit) = temp.split()[3:] # We only want temp format
                temp = Weather._getTemp(float(temp), deg, unit, msg.args[0])
                resp = ['The current temperature in %s is %s (%s).' %\
                        (location, temp, time)]
                conds = info['Conditions']
                resp.append('Conditions: %s.' % info['Conditions'])
                humidity = info['Humidity']
                resp.append('Humidity: %s.' % info['Humidity'])
                # Apparently, the "Dew Point" and "Wind" categories are
                # occasionally set to "-" instead of an actual reading. So,
                # we'll just catch the ValueError from trying to unpack a tuple
                # of the wrong size.
                try:
                    (dew, deg, unit) = info['Dew Point'].split()[3:]
                    dew = Weather._getTemp(float(dew), deg, unit, msg.args[0])
                    resp.append('Dew Point: %s.' % dew)
                except (ValueError, KeyError):
                    pass
                try:
                    wind = 'Wind: %s at %s %s.' % tuple(info['Wind'].split())
                    resp.append(wind)
                except (ValueError, TypeError):
                    pass
                try:
                    (chill, deg, unit) = info['Windchill'].split()[3:]
                    chill = Weather._getTemp(float(chill), deg,
                                             unit, msg.args[0])
                    resp.append('Windchill: %s.' % chill)
                except (ValueError, KeyError):
                    pass
                if info['Pressure']:
                    resp.append('Pressure: %s.' % info['Pressure'])
                resp.append(severe)
                resp = map(utils.web.htmlToText, resp)
                irc.reply(' '.join(resp).decode('latin1').encode('utf-8'))
            else:
                Weather._noLocation()
        wunder = wrap(wunder, ['text'])

        _rsswunderUrl = 'http://www.wunderground.com/cgi-bin/findweather/' \
                        'getForecast?query=%s'
        _rsswunderfeed = re.compile(
            r'<link rel="alternate".*href="([^"]+)" */?>', re.I)
        _rsswunderSevere = re.compile(
            r'font color="?#ff0000"?><b>([^<]+)<', re.I)
        _rsswunderLocation = re.compile(
            r'<title>(?:(.*) Weather from Weather Underground|'
            r'Weather Underground - (.*))</title>', re.I)
        _rsswunderForecastDate = re.compile(r'Forecast for (.*) as of', re.I)
        def rss(self, irc, msg, args, loc):
            """<US zip code | US/Canada city, state | Foreign city, country>

            Returns the approximate weather conditions for a given city.
            """
            url = self._rsswunderUrl % utils.web.urlquote(loc)
            url = url.replace('%20', '+')
            text = utils.web.getUrl(url)
            if 'Search not found' in text or \
               re.search(r'size="2"> Place </font>', text, re.I):
                Weather._noLocation()
            if 'Search Results' in text:
                m = self._backupUrl.search(text)
                if m is not None:
                    url = 'http://www.wunderground.com' + m.group(1)
                    text = utils.web.getUrl(url)
                else:
                    Weather._noLocation()
            self._rss(irc, text)
        rss = wrap(rss, ['text'])

        def _rss(self, irc, text):
            severe = None
            m = self._rsswunderSevere.search(text)
            if m:
                severe = ircutils.bold(m.group(1))
            feed = self._rsswunderfeed.search(text)
            if not feed:
                Weather._noLocation()
            feed = feed.group(1)
            rss = utils.web.getUrl(feed)
            rss = self._formatSymbols(rss)
            rss = rss.replace(":", ": ")
            rss = rss.replace(":  ", ": ")
            resp = []
            location = self._rsswunderLocation.search(rss)
            if location is not None:
                title = filter(None, location.groups())
                if title:
                    resp.append('Weather for %s' % title[0])
            info = feedparser.parse(rss)
            for e in info['entries']:
                d = self._rsswunderForecastDate.search(e['title'])
                if d is not None:
                    resp.append(d.group(1) + ' - Conditions: ' + e['summary'])
                else:
                    resp.append(e['summary'])
            resp = [s.encode('utf-8').rstrip('.') for s in resp]
            if severe is not None:
                resp.append(severe)
            irc.reply(utils.web.htmlToText('; '.join(resp)))

        def _formatSymbols(self, text):
            text = text.replace("&amp;", "&")
            text = text.replace("&#176;", "&deg;")
            text = text.replace(" &deg; ", "&deg;")
            text = text.replace("&deg;", "\xb0")
            return text

Class = Weather


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
