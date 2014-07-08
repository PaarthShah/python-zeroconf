#!/usr/bin/env python

""" Unit tests for zeroconf.py """

import socket
import struct
import unittest
from time import sleep

import zeroconf as r
from zeroconf import byte_ord, ServiceBrowser, ServiceInfo, xrange, Zeroconf


class PacketGeneration(unittest.TestCase):

    def testParseOwnPacketSimple(self):
        generated = r.DNSOutgoing(0)
        r.DNSIncoming(generated.packet())

    def testParseOwnPacketSimpleUnicast(self):
        generated = r.DNSOutgoing(0, 0)
        r.DNSIncoming(generated.packet())

    def testParseOwnPacketFlags(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        r.DNSIncoming(generated.packet())

    def testParseOwnPacketQuestion(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        generated.addQuestion(r.DNSQuestion("testname.local.", r._TYPE_SRV,
                                            r._CLASS_IN))
        r.DNSIncoming(generated.packet())

    def testMatchQuestion(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        question = r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        generated.addQuestion(question)
        parsed = r.DNSIncoming(generated.packet())
        self.assertEqual(len(generated.questions), 1)
        self.assertEqual(len(generated.questions), len(parsed.questions))
        self.assertEqual(question, parsed.questions[0])


class PacketForm(unittest.TestCase):

    def testTransactionID(self):
        """ID must be zero in a DNS-SD packet"""
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        bytes = generated.packet()
        id = byte_ord(bytes[0]) << 8 | byte_ord(bytes[1])
        self.assertEqual(id, 0)

    def testQueryHeaderBits(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_QUERY)
        bytes = generated.packet()
        flags = byte_ord(bytes[2]) << 8 | byte_ord(bytes[3])
        self.assertEqual(flags, 0x0)

    def testResponseHeaderBits(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        bytes = generated.packet()
        flags = byte_ord(bytes[2]) << 8 | byte_ord(bytes[3])
        self.assertEqual(flags, 0x8000)

    def testNumbers(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        bytes = generated.packet()
        (numQuestions, numAnswers, numAuthorities,
         numAdditionals) = struct.unpack('!4H', bytes[4:12])
        self.assertEqual(numQuestions, 0)
        self.assertEqual(numAnswers, 0)
        self.assertEqual(numAuthorities, 0)
        self.assertEqual(numAdditionals, 0)

    def testNumbersQuestions(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion("testname.local.", r._TYPE_SRV, r._CLASS_IN)
        for i in xrange(10):
            generated.addQuestion(question)
        bytes = generated.packet()
        (numQuestions, numAnswers, numAuthorities,
         numAdditionals) = struct.unpack('!4H', bytes[4:12])
        self.assertEqual(numQuestions, 10)
        self.assertEqual(numAnswers, 0)
        self.assertEqual(numAuthorities, 0)
        self.assertEqual(numAdditionals, 0)


class Names(unittest.TestCase):

    def testLongName(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion("this.is.a.very.long.name.with.lots.of.parts.in.it.local.",
                                 r._TYPE_SRV, r._CLASS_IN)
        generated.addQuestion(question)
        r.DNSIncoming(generated.packet())

    def testExceedinglyLongName(self):
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        name = "%slocal." % ("part." * 1000)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.addQuestion(question)
        r.DNSIncoming(generated.packet())

    def testExceedinglyLongNamePart(self):
        name = "%s.local." % ("a" * 1000)
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.addQuestion(question)
        self.assertRaises(r.NamePartTooLongException, generated.packet)

    def testSameName(self):
        name = "paired.local."
        generated = r.DNSOutgoing(r._FLAGS_QR_RESPONSE)
        question = r.DNSQuestion(name, r._TYPE_SRV, r._CLASS_IN)
        generated.addQuestion(question)
        generated.addQuestion(question)
        r.DNSIncoming(generated.packet())


class Framework(unittest.TestCase):

    def testLaunchAndClose(self):
        rv = r.Zeroconf()
        rv.close()


def test_integration():

    services = set()

    class Listener(object):

        def removeService(self, zeroconf, type_, name):
            print('remove')
            services.remove((type_, name))

        def addService(self, zeroconf, type_, name):
            print('add')
            services.add((type_, name))

    type_ = "_http._tcp.local."

    zeroconf_browser = Zeroconf()
    listener = Listener()
    browser = ServiceBrowser(zeroconf_browser, type_, listener)

    zeroconf_registrar = Zeroconf()
    desc = {'path': '/~paulsm/'}
    name = "xxxyyy.%s" % type_
    info = ServiceInfo(
        type_, name,
        socket.inet_aton("10.0.1.2"), 80, 0, 0,
        desc, "ash-2.local.")
    zeroconf_registrar.registerService(info)

    # TODO replace those blind sleeps with events
    sleep(2)
    try:
        assert (type_, name) in services, services
        zeroconf_registrar.unregisterService(info)
        sleep(2)
        assert (type_, name) not in services, services
    finally:
        zeroconf_registrar.close()
        browser.cancel()
        zeroconf_browser.close()
