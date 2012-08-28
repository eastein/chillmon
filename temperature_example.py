import time
import mcp3008

a2d = mcp3008.MCP3008(3300.0)
temperature = mcp3008.TMP36(mcp3008.TMP36.C)
a2d.setup_channel(0, temperature)

while True:
	print '%0.1f C' % temperature.read()
        time.sleep(1)
