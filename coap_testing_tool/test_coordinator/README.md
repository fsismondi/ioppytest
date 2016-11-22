Test coordinator component.

Reads test extended description, and dispatches orders to other components

Dispatches orders related to:
	- sniffing
	- analysis
	- step execution
	- dissection


DONE:
	- AMQP interface between coord and test-gui
	- Test with 3 CoAP test cases

TODO:
	- implement calls to  analysis component, dissection component
and sniffing component with AMQP
	- test with a 6tisch example
	- adapt it the case where we have two users and not just one user agains
an automated IUT
	- adapt coord for 'step by step' mode of analysis

For more info go to:
	http://doc.f-interop.eu/#test-coordinator
