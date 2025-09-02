# --- 0. IMPORT NECESSARY LIBRARIES ---
# These are the "toolkits" we need to make the app work.

# base64 and io are used for handling the file upload process.
import base64
import io

# pandas is a powerful library for data manipulation (like reading CSVs and preparing our data).
import pandas as pd

# plotly.graph_objects is used for adding layers to our plot.
import plotly.graph_objects as go
# Import plotly.express to access its color palettes.
import plotly.express as px

# dash and its components (dcc, html) are the core framework for building the web application itself.
import dash
from dash import dcc, html, clientside_callback, ClientsideFunction
from dash.dependencies import Input, Output, State, ALL

# --- 1. INITIALIZE THE DASH APP ---
# This line creates the actual Dash web application.
app = dash.Dash(__name__, suppress_callback_exceptions=True)
# This line is needed for deployment on services like Render.
server = app.server

# --- 2. DEFINE THE APP LAYOUT ---
# This section defines the visual structure of your web page using Python.
app.layout = html.Div(style={'backgroundColor': '#1E1E1E', 'color': 'white', 'fontFamily': 'sans-serif', 'display': 'flex', 'height': '100vh'}, children=[
    
    # --- LEFT CONTROL PANEL ---
    html.Div(style={'width': '25%', 'padding': '20px', 'display': 'flex', 'flexDirection': 'column'}, children=[
        html.H2('Flight Visualizer'),
        html.Hr(),
        html.H4('Upload Data'),
        dcc.Upload(
            id='upload-data',
            children=html.Div(['Drag and Drop or ', html.A('Select a File')]),
            style={
                'width': '100%', 'height': '60px', 'lineHeight': '60px',
                'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
                'textAlign': 'center', 'margin': '10px 0', 'color': 'white',
                'borderColor': '#666'
            },
            multiple=False
        ),
        html.Button("Download Template CSV", id="btn-download-template", 
                    style={'marginTop': '10px', 'backgroundColor': '#444', 'color': 'white', 'border': 'none', 'padding': '10px', 'borderRadius': '5px'}),
        dcc.Download(id="download-template-csv"),
        html.Hr(),
        html.H4('Animation Smoothness'),
        html.P('Frames per hour: 30', id='slider-output', style={'textAlign': 'center'}),
        dcc.Slider(
            id='frames-slider', min=30, max=120, step=15, value=30,
            marks={i: str(i) for i in range(30, 121, 15)},
        )
    ]),

    # --- RIGHT GRAPH PANEL ---
    html.Div(style={'width': '75%', 'padding': '10px', 'height': '100%', 'display': 'flex', 'flexDirection': 'column'}, children=[
        dcc.Loading(
            id="loading-icon",
            type="circle",
            children=html.Div(id='output-graph-container', style={'flex': '1', 'minHeight': '0'})
        )
    ])
])


# --- 3. DEFINE THE CALLBACK FUNCTIONS (THE APP'S "BRAIN") ---

# --- CALLBACK 1: UPDATE THE GRAPH ---
@app.callback(
    Output('output-graph-container', 'children'),
    Input('upload-data', 'contents'),
    Input('frames-slider', 'value'),
    State('upload-data', 'filename')
)
def update_graph(contents, frames_per_hour, filename):
    if contents is not None:
        content_type, content_string = contents.split(',')
        decoded = base64.b64decode(content_string)
        
        try:
            df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
            df.columns = df.columns.str.strip()

            required_columns = [
                'flight_id', 'origin_code', 'origin_lat', 'origin_lon',
                'destination_code', 'dest_lat', 'dest_lon', 'departure_time', 'arrival_time'
            ]
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return html.Div(f"Error: The uploaded file is missing columns: {', '.join(missing_columns)}", 
                                style={'color': 'red', 'textAlign': 'center', 'paddingTop': '50px'})
            
            # --- DATA PREPARATION AND DENSIFICATION ---
            df['departure_time'] = pd.to_datetime(df['departure_time'])
            df['arrival_time'] = pd.to_datetime(df['arrival_time'])
            start_time = df['departure_time'].min()
            end_time = df['arrival_time'].max()
            total_hours = (end_time - start_time).total_seconds() / 3600
            total_frames = max(int(total_hours * frames_per_hour), 1)
            animation_timestamps = pd.date_range(start=start_time, end=end_time, periods=total_frames)

            densified_data = []
            for timestamp in animation_timestamps:
                for i, flight in df.iterrows():
                    if flight['departure_time'] <= timestamp <= flight['arrival_time']:
                        flight_duration = (flight['arrival_time'] - flight['departure_time']).total_seconds()
                        time_elapsed = (timestamp - flight['departure_time']).total_seconds()
                        progress_ratio = time_elapsed / flight_duration if flight_duration > 0 else 0
                        current_lat = flight['origin_lat'] + (flight['dest_lat'] - flight['origin_lat']) * progress_ratio
                        current_lon = flight['origin_lon'] + (flight['dest_lon'] - flight['origin_lon']) * progress_ratio
                        densified_data.append({
                            'flight_id': flight['flight_id'], 
                            'origin_code': flight['origin_code'],
                            'Frame': timestamp, 
                            'Current_Lat': current_lat, 
                            'Current_Lon': current_lon
                        })

            if not densified_data:
                 return html.Div("No flights found in the given time range.", 
                                 style={'textAlign': 'center', 'paddingTop': '50px', 'color': 'orange'})
            
            densified_df = pd.DataFrame(densified_data)
            
            # --- PLOTTING PREPARATION ---
            all_airports = pd.unique(df[['origin_code', 'destination_code']].values.ravel('K'))
            bright_colors = [
                '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
                '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2'
            ]
            airport_colors = {airport: bright_colors[i % len(bright_colors)] for i, airport in enumerate(all_airports)}
            
            origin_airports = df[['origin_code', 'origin_lat', 'origin_lon']].rename(
                columns={'origin_code': 'code', 'origin_lat': 'lat', 'origin_lon': 'lon'})
            dest_airports = df[['destination_code', 'dest_lat', 'dest_lon']].rename(
                columns={'destination_code': 'code', 'dest_lat': 'lat', 'dest_lon': 'lon'})
            all_airport_locations = pd.concat([origin_airports, dest_airports]).drop_duplicates(subset='code').reset_index(drop=True)

            def calculate_bearing(lat1, lon1, lat2, lon2):
                import math
                lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
                dlon = lon2 - lon1
                y = math.sin(dlon) * math.cos(lat2)
                x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
                bearing = math.atan2(y, x)
                bearing = math.degrees(bearing)
                bearing = (bearing + 360) % 360
                return bearing

            bearing_map = {flight['flight_id']: calculate_bearing(flight['origin_lat'], flight['origin_lon'], flight['dest_lat'], flight['dest_lon']) for i, flight in df.iterrows()}
            densified_df['bearing'] = densified_df['flight_id'].map(bearing_map)
            
            # FIX: Create a dedicated hover text column to avoid the silent error.
            densified_df['hover_text'] = '<b>' + densified_df['flight_id'] + '</b><br>Origin: ' + densified_df['origin_code']

            # --- CREATE THE INTERACTIVE PLOTLY FIGURE ---
            fig = go.Figure()
            
            initial_frame_df = densified_df[densified_df['Frame'] == densified_df['Frame'].min()]
            
            # Layer 1: Animated planes - using origin_code for color mapping
            fig.add_trace(go.Scattermap(
                name="Planes",
                lat=initial_frame_df['Current_Lat'], 
                lon=initial_frame_df['Current_Lon'],
                mode='markers',
                marker=dict(
                    size=12, 
                    symbol='triangle',
                    angle=initial_frame_df['bearing'],
                    color=initial_frame_df['origin_code'].map(airport_colors) # This will now work correctly
                ),
                # FIX: Use the pre-formatted text column.
                text=initial_frame_df['hover_text'],
                hoverinfo='text',
                showlegend=False
            ))
            
            # Layer 2: Static airports - using airport code for color mapping
            airport_marker_colors = [airport_colors.get(code) for code in all_airport_locations['code']]
            fig.add_trace(go.Scattermap(
                name="Airports",
                lat=all_airport_locations['lat'], 
                lon=all_airport_locations['lon'],
                mode='markers+text',
                marker=dict(
                    size=15, 
                    color=airport_marker_colors
                ),
                text=all_airport_locations['code'], 
                textposition="top right",
                hovertemplate='<b>%{text}</b><extra></extra>',
                showlegend=False
            ))

            # --- CREATE ANIMATION FRAMES ---
            frames = []
            for i, timestamp in enumerate(densified_df['Frame'].unique()):
                frame_df = densified_df[densified_df['Frame'] == timestamp]
                frame = go.Frame(
                    data=[
                        go.Scattermap(
                            lat=frame_df['Current_Lat'], 
                            lon=frame_df['Current_Lon'],
                            marker=dict(
                                size=12, 
                                symbol='triangle',
                                angle=frame_df['bearing'],
                                color=frame_df['origin_code'].map(airport_colors) # Color mapping applied here
                            ),
                            # FIX: Use the pre-formatted text column.
                            text=frame_df['hover_text'],
                            hoverinfo='text'
                        ),
                        go.Scattermap() # Placeholder for the static airport trace
                    ],
                    traces=[0, 1],
                    name=str(i)
                )
                frames.append(frame)
            
            fig.frames = frames

            # Add animation controls using Plotly's built-in controls
            sliders = [dict(
                steps=[dict(
                    args=[[frame.name], {"frame": {"duration": 100, "redraw": True}, "mode": "immediate", "transition": {"duration": 50}}],
                    label=pd.to_datetime(animation_timestamps[i]).strftime('%H:%M'),
                    method="animate"
                ) for i, frame in enumerate(frames)],
                active=0,
                currentvalue={"prefix": "Time: ", "font": {"size": 16}},
                transition={"duration": 50},
                x=0.1, len=0.9, xanchor="left", y=0.1, yanchor="top"
            )]

            play_button = [dict(
                type="buttons",
                showactive=False,
                y=0.1, x=0, xanchor="left", yanchor="top",
                pad={"t": 0, "r": 10},
                buttons=[
                    dict(label="▶ Play", method="animate", args=[None, {"frame": {"duration": 200, "redraw": True}, "fromcurrent": True, "transition": {"duration": 100}}]),
                    dict(label="❚❚ Pause", method="animate", args=[[None], {"frame": {"duration": 0, "redraw": False}, "mode": "immediate", "transition": {"duration": 0}}])
                ]
            )]

            # --- CONFIGURE LAYOUT ---
            fig.update_layout(
                map_style="carto-positron",
                margin={"r":0,"t":50,"l":0,"b":100},
                paper_bgcolor='#1E1E1E',
                plot_bgcolor='#1E1E1E',
                font=dict(color='white'),
                sliders=sliders,
                updatemenus=play_button,
                height=800
            )
            
            return dcc.Graph(id='flight-map', figure=fig, style={'height': '100%'})

        except Exception as e:
            print(f"Error processing file: {e}")
            return html.Div([
                f'Error: {str(e)}', 
                html.Br(),
                'Please check that your CSV has the required columns and proper date formatting.'
            ], style={'color': 'red', 'textAlign': 'center', 'paddingTop': '50px'})
            
    return html.Div("Please upload a file to begin.", style={'textAlign': 'center', 'paddingTop': '50px'})

# --- CALLBACK 2: UPDATE UPLOAD BUTTON TEXT ---
@app.callback(
    Output('upload-data', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def update_upload_text(contents, filename):
    if contents is not None:
        return html.Div([f"Loaded: {filename}. ", html.A("Change CSV?")])
    else:
        return html.Div(['Drag and Drop or ', html.A('Select a File')])

# --- CALLBACK 3: UPDATE SLIDER LABEL ---
@app.callback(
    Output('slider-output', 'children'),
    Input('frames-slider', 'value')
)
def update_slider_output(value):
    return f"Frames per hour: {value}"

# --- CALLBACK 4: HANDLE TEMPLATE DOWNLOAD ---
@app.callback(
    Output("download-template-csv", "data"),
    Input("btn-download-template", "n_clicks"),
    prevent_initial_call=True,
)
def download_template(n_clicks):
    template_df = pd.DataFrame([
        {
            "flight_id": "EX101", "airline": "ExampleAir", "origin_code": "DEL",
            "origin_lat": 28.5665, "origin_lon": 77.1031, "destination_code": "BOM",
            "dest_lat": 19.0896, "dest_lon": 72.8656,
            "departure_time": "2025-10-01 07:00:00", "arrival_time": "2025-10-01 09:05:00"
        }
    ])
    # FIX: Correctly use dcc.send_string with the CSV data.
    return dcc.send_string(template_df.to_csv(index=False), "flight_template.csv")

# --- 5. RUN THE APP ---
if __name__ == '__main__':
    app.run(debug=True)

