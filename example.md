curl -X GET http://127.0.0.1:5000/start_execution

curl -X GET http://127.0.0.1:5000/stop_execution

curl -X GET http://127.0.0.1:5000/current_codel

curl -X POST http://127.0.0.1:5000/set_color \
     -H "Content-Type: application/json" \
     -d '{"x": 10, "y": 5, "color": "red"}'

curl -X POST http://127.0.0.1:5000/clear_color \
     -H "Content-Type: application/json" \
     -d '{"x": 10, "y": 5}'

curl -X GET http://127.0.0.1:5000/get_board

curl -X GET http://127.0.0.1:5000/get_dimensions

curl -X GET http://127.0.0.1:5000/render

curl -X POST http://127.0.0.1:5000/set_terminal_size \
     -H "Content-Type: application/json" \
     -d '{"rows": 24, "cols": 80}'
