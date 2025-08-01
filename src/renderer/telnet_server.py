import asyncio
import telnetlib3
import aiohttp

HOST = '0.0.0.0'
PORT = 8023

async def run_game(reader, writer):
    writer.write("Loading PietWars... Press 'q' to return.\n")
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                resp = await session.get('http://api:5000/render')
                text = await resp.text()
                if text.startswith('<pre>'):
                    board = text[5:-6]
                else:
                    board = text
            except Exception:
                board = "Failed to fetch board." 
            writer.write('\x1b[2J\x1b[H')
            writer.write(board + '\n')
            writer.write("(press 'q' to exit game)\n")
            await writer.drain()
            try:
                key = await asyncio.wait_for(reader.read(1), timeout=1.0)
                if key.lower() == 'q':
                    break
            except asyncio.TimeoutError:
                continue

async def games_menu(reader, writer):
    while True:
        writer.write("\nGames Menu\n1. PietWars\n2. Back\nSelection: ")
        choice = (await reader.readline()).strip()
        if choice == '1':
            await run_game(reader, writer)
        elif choice == '2':
            return
        else:
            writer.write("Invalid option.\n")

async def shell(reader, writer):
    writer.write("Welcome to PietChan BBS!\n")
    while True:
        writer.write("\nMain Menu\n1. /p/ Programming\n2. /g/ Games\n3. Quit\nSelection: ")
        choice = (await reader.readline()).strip()
        if choice == '1':
            writer.write("You opened /p/ Programming.\n")
        elif choice == '2':
            await games_menu(reader, writer)
        elif choice == '3' or choice.lower() == 'quit':
            writer.write("Goodbye!\n")
            break
        else:
            writer.write("Invalid option.\n")
    writer.close()

async def main():
    server = await telnetlib3.create_server(host=HOST, port=PORT, shell=shell)
    await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
