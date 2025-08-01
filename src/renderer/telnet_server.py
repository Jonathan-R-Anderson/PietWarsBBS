import asyncio
import telnetlib3
import aiohttp

HOST = '0.0.0.0'
PORT = 8023

async def run_game(reader, writer):
    try:
        writer.write("Loading PietWars... Press 'q' to return.\n")
    except Exception:
        return
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
            try:
                writer.write('\x1b[2J\x1b[H')
                writer.write(board + '\n')
                writer.write("(press 'q' to exit game)\n")
                await writer.drain()
            except Exception:
                break
            try:
                key = await asyncio.wait_for(reader.read(1), timeout=1.0)
                if key.lower() == 'q':
                    break
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

async def games_menu(reader, writer):
    while True:
        try:
            # Clear the screen and move the cursor to the top before rendering the menu
            writer.write("\x1b[2J\x1b[H")
            writer.write("Games Menu\n1. PietWars\n2. Back\nSelection: ")
        except Exception:
            break
        choice = (await reader.readline()).strip()
        if choice == '1':
            await run_game(reader, writer)
        elif choice == '2':
            return
        else:
            try:
                writer.write("Invalid option.\n")
            except Exception:
                break

async def shell(reader, writer):
    try:
        writer.write("Welcome to PietChan BBS!\n")
    except Exception:
        return
    while True:
        try:
            # Clear the screen and position the cursor at the top before showing the menu
            writer.write("\x1b[2J\x1b[H")
            writer.write("Main Menu\n1. /p/ Programming\n2. /g/ Games\n3. Quit\nSelection: ")
        except Exception:
            break
        choice = (await reader.readline()).strip()
        if choice == '1':
            try:
                writer.write("You opened /p/ Programming.\n")
            except Exception:
                break
        elif choice == '2':
            await games_menu(reader, writer)
        elif choice == '3' or choice.lower() == 'quit':
            try:
                writer.write("Goodbye!\n")
            except Exception:
                pass
            break
        else:
            try:
                writer.write("Invalid option.\n")
            except Exception:
                break
    writer.close()

async def main():
    server = await telnetlib3.create_server(host=HOST, port=PORT, shell=shell)
    await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
