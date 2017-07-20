# Test coordinator component.

Reads test extended description, and dispatches orders to other components.

All communication happens though the AMQP event bus.
    see http://doc.f-interop.eu for more info

Dispatches orders related to:
	- sniffing (e.g. start sniffing)
	- analysis (e.g. analyse frames for testcase x)
	- testcoordination ( e.g. step stimuli execute)
	- dissection ( e.g. dissect frames )
	- agent (e.g. start tun interface)

For more info go to:
	http://doc.f-interop.eu/#test-coordinator
