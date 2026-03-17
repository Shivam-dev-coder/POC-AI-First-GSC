# Marks tools as a Python package.
#
# Each tool module (driver, stops, products) exposes a register(mcp) function
# that attaches its tools to the FastMCP instance. server.py calls each one
# at startup.
