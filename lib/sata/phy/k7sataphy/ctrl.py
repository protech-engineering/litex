from math import ceil

from migen.fhdl.std import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.genlib.fsm import FSM, NextState
from migen.flow.actor import Sink, Source

from lib.sata.std import *

def us(t, clk_freq):
	clk_period_us = 1000000/clk_freq
	return ceil(t/clk_period_us)

class K7SATAPHYHostCtrl(Module):
	def __init__(self, gtx, crg, clk_freq):
		self.ready = Signal()

		self.sink = Sink([("data", 32), ("charisk", 4)])
		self.source = Source([("data", 32), ("charisk", 4)])

		self.align_detect = align_detect = Signal()
		align_timeout_cnt = Signal(32)
		align_timeout = Signal()

		retry_timeout_cnt = Signal(32)
		retry_timeout = Signal()

		non_align_cnt = Signal(4)

		txcominit = Signal()
		txcomwake = Signal()

		self.comb += [
			self.source.stb.eq(1),
			self.sink.ack.eq(1)
		]

		fsm = FSM(reset_state="RESET")
		self.submodules += fsm

		fsm.act("RESET",
			gtx.txelecidle.eq(1),
			If(crg.ready,
				NextState("COMINIT")
			),
		)
		fsm.act("COMINIT",
			gtx.txelecidle.eq(1),
			txcominit.eq(1),
			If(gtx.txcomfinish & ~gtx.rxcominitdet,
				NextState("AWAIT_COMINIT")
			),
		)
		fsm.act("AWAIT_COMINIT",
			gtx.txelecidle.eq(1),
			If(gtx.rxcominitdet,
				NextState("AWAIT_NO_COMINIT")
			).Else(
				If(retry_timeout,
					NextState("RESET")
				)
			),
		)
		fsm.act("AWAIT_NO_COMINIT",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcominitdet,
				NextState("CALIBRATE")
			),
		)
		fsm.act("CALIBRATE",
			gtx.txelecidle.eq(1),
			NextState("COMWAKE"),
		)
		fsm.act("COMWAKE",
			gtx.txelecidle.eq(1),
			txcomwake.eq(1),
			If(gtx.txcomfinish,
				NextState("AWAIT_COMWAKE")
			),
		)
		fsm.act("AWAIT_COMWAKE",
			gtx.txelecidle.eq(1),
			If(gtx.rxcomwakedet,
				NextState("AWAIT_NO_COMWAKE")
			).Else(
				If(retry_timeout,
					NextState("RESET")
				)
			),
		)
		fsm.act("AWAIT_NO_COMWAKE",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcomwakedet,
				NextState("AWAIT_NO_RXELECIDLE")
			),
		)
		fsm.act("AWAIT_NO_RXELECIDLE",
			gtx.txelecidle.eq(0),
			self.source.data.eq(0x4A4A4A4A), #D10.2
			self.source.charisk.eq(0b0000),
			If(~gtx.rxelecidle,
				NextState("AWAIT_ALIGN"),
				crg.reset.eq(1),
				gtx.pmarxreset.eq(1)
			),
		)
		fsm.act("AWAIT_ALIGN",
			gtx.txelecidle.eq(0),
			self.source.data.eq(0x4A4A4A4A), #D10.2
			self.source.charisk.eq(0b0000),
			gtx.rxalign.eq(1),
			If((align_detect & ~gtx.rxelecidle) & ~align_timeout,
				NextState("SEND_ALIGN")
			).Elif(~align_detect & align_timeout,
				NextState("RESET")
			),
		)
		fsm.act("SEND_ALIGN",
			gtx.txelecidle.eq(0),
			self.source.data.eq(primitives["ALIGN"]),
			self.source.charisk.eq(0b0001),
			If(non_align_cnt == 3,
				NextState("READY")
			),
		)
		fsm.act("READY",
			gtx.txelecidle.eq(0),
			self.source.data.eq(primitives["SYNC"]),
			self.source.charisk.eq(0b0001),
			self.ready.eq(1),
		)

		txcominit_d = Signal()
		txcomwake_d = Signal()
		self.sync += [
			txcominit_d.eq(txcominit),
			txcomwake_d.eq(txcomwake),
			gtx.txcominit.eq(txcominit & ~txcominit_d),
			gtx.txcomwake.eq(txcomwake & ~txcomwake_d),
		]

		self.comb +=  align_detect.eq(self.sink.stb & (self.sink.data == primitives["ALIGN"]));
		self.sync += \
			If(fsm.ongoing("RESET"),
				align_timeout_cnt.eq(us(873, clk_freq))
			).Elif(fsm.ongoing("AWAIT_ALIGN"),
				align_timeout_cnt.eq(align_timeout_cnt-1)
			)
		self.comb += align_timeout.eq(align_timeout_cnt == 0)

		self.sync += \
			If(fsm.ongoing("RESET") | fsm.ongoing("AWAIT_NO_COMINIT"),
				retry_timeout_cnt.eq(us(10000, clk_freq))
			).Elif(fsm.ongoing("AWAIT_COMINIT") | fsm.ongoing("AWAIT_COMWAKE"),
				retry_timeout_cnt.eq(retry_timeout_cnt-1)
			)
		self.comb += retry_timeout.eq(retry_timeout_cnt == 0)

		self.sync += \
			If(fsm.ongoing("SEND_ALIGN"),
				If(self.sink.stb,
					If(self.sink.data[0:8] == 0x7C,
						non_align_cnt.eq(non_align_cnt + 1)
					).Else(
						non_align_cnt.eq(0)
					)
				)
			)

class K7SATAPHYDeviceCtrl(Module):
	def __init__(self, gtx, crg, clk_freq):
		self.ready = Signal()

		self.sink = Sink([("data", 32), ("charisk", 4)])
		self.source = Source([("data", 32), ("charisk", 4)])

		align_detect = Signal()
		align_timeout = Signal()
		align_timeout_cnt = Signal(32)

		retry_timeout_cnt = Signal(32)
		retry_timeout = Signal()

		txcominit = Signal()
		txcomwake = Signal()

		self.comb += [
			self.source.stb.eq(1),
			self.sink.ack.eq(1)
		]

		fsm = FSM(reset_state="RESET")
		self.submodules += fsm

		fsm.act("RESET",
			gtx.txelecidle.eq(1),
			If(crg.ready,
				NextState("AWAIT_COMINIT")
			)
		)
		fsm.act("AWAIT_COMINIT",
			gtx.txelecidle.eq(1),
			If(gtx.rxcominitdet,
				NextState("AWAIT_NO_COMINIT")
			)
		)
		fsm.act("AWAIT_NO_COMINIT",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcominitdet,
				NextState("COMINIT")
			)
		)
		fsm.act("COMINIT",
			gtx.txelecidle.eq(1),
			txcominit.eq(1),
			If(gtx.txcomfinish,
				NextState("AWAIT_COMWAKE")
			)
		)
		fsm.act("AWAIT_COMWAKE",
			gtx.txelecidle.eq(1),
			If(gtx.rxcomwakedet,
				NextState("AWAIT_NO_COMWAKE")
			).Else(
				If(retry_timeout,
					NextState("RESET")
				)
			)
		)
		fsm.act("AWAIT_NO_COMWAKE",
			gtx.txelecidle.eq(1),
			If(~gtx.rxcomwakedet,
				NextState("CALIBRATE")
			)
		)
		fsm.act("CALIBRATE",
			gtx.txelecidle.eq(1),
			NextState("COMWAKE")
		)
		fsm.act("COMWAKE",
			gtx.txelecidle.eq(1),
			txcomwake.eq(1),
			If(gtx.txcomfinish,
				NextState("RESET_CRG"),
				crg.reset.eq(1),
			)
		)
		fsm.act("RESET_CRG",
			gtx.txelecidle.eq(0),
			If(crg.ready,
				NextState("SEND_ALIGN")
			)
		)
		fsm.act("SEND_ALIGN",
			gtx.txelecidle.eq(0),
			gtx.rxalign.eq(1),
			self.source.data.eq(primitives["ALIGN"]),
			self.source.charisk.eq(0b0001),
			If(align_detect,
				NextState("READY")
			).Elif(align_timeout,
				NextState("ERROR")
			)
		)
		fsm.act("READY",
			gtx.txelecidle.eq(0),
			NextState("READY"),
			If(gtx.rxelecidle,
				NextState("RESET")
			),
			self.ready.eq(1)
		)
		fsm.act("ERROR",
			gtx.txelecidle.eq(1),
			NextState("RESET")
		)

		txcominit_d = Signal()
		txcomwake_d = Signal()
		self.sync += [
			txcominit_d.eq(txcominit),
			txcomwake_d.eq(txcomwake),
			gtx.txcominit.eq(txcominit & ~txcominit_d),
			gtx.txcomwake.eq(txcomwake & ~txcomwake_d),
		]

		self.comb +=  align_detect.eq(self.sink.stb & (self.sink.data == primitives["ALIGN"]));
		self.sync += \
			If(fsm.ongoing("RESET"),
				align_timeout_cnt.eq(us(55, clk_freq))
			).Elif(fsm.ongoing("AWAIT_ALIGN"),
				align_timeout_cnt.eq(align_timeout_cnt-1)
			)
		self.comb += align_timeout.eq(align_timeout_cnt == 0)

		self.sync += \
			If(fsm.ongoing("RESET"),
				retry_timeout_cnt.eq(us(10000, clk_freq))
			).Elif(fsm.ongoing("AWAIT_COMWAKE"),
				retry_timeout_cnt.eq(retry_timeout_cnt-1)
			)
		self.comb += retry_timeout.eq(retry_timeout_cnt == 0)
