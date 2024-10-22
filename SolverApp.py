from flask import Flask, render_template, request
import pandas as pd
from pulp import *

# Initialize Flask app
app = Flask(__name__)

# Load data and initialize variables
df = pd.read_pickle('C:/Users/Sam Bailey/Documents/Data Science/Solver App/projections.pkl')
columns_to_convert = ["DK Salary", "DK Projection", "DK Value", "DK Large Ownership", "DK Small Ownership", "DK Floor", "DK Ceiling"]
df[columns_to_convert] = df[columns_to_convert].apply(pd.to_numeric, errors='coerce')

availables = df
salaries = {}
points = {}
owns = {}
ceilings = {}

for pos in availables.Position.unique():
    available_pos = availables[availables.Position == pos]
    salary = list(available_pos[["Player","DK Salary"]].set_index("Player").to_dict().values())[0]
    point = list(available_pos[["Player","DK Projection"]].set_index("Player").to_dict().values())[0]
    own = list(available_pos[["Player","DK Large Ownership"]].set_index("Player").to_dict().values())[0]
    ceil = list(available_pos[["Player","DK Ceiling"]].set_index("Player").to_dict().values())[0]
    
    # Standardize player names by replacing spaces and periods with underscores
    salary = {player.replace(" ", "_").replace(".", ""): value for player, value in salary.items()}
    point = {player.replace(" ", "_").replace(".", ""): value for player, value in point.items()}
    own = {player.replace(" ", "_").replace(".", ""): value for player, value in own.items()}
    ceil = {player.replace(" ", "_").replace(".", ""): value for player, value in ceil.items()}
    
    salaries[pos] = salary
    points[pos] = point
    owns[pos] = own
    ceilings[pos] = ceil

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Retrieve form data
        pos_num_available = {
            "QB": int(request.form['QB']),
            "RB": int(request.form['RB']),
            "WR": int(request.form['WR']),
            "TE": int(request.form['TE']),
            "FLEX": int(request.form['FLEX']),
            "DST": int(request.form['DST'])
        }
        SALARY_CAP = int(request.form['SALARY_CAP'])
        OWN_CEILING = int(request.form['OWN_CEILING'])
        CEIL_FLOOR = int(request.form['CEIL_FLOOR'])

        # Set up LP Problem
        prob = LpProblem("Fantasy", LpMaximize)
        _vars = {k: LpVariable.dict(k, v, cat="Binary") for k, v in owns.items()}
        rewards = []
        costs = []
        own_constraints = []
        ceil_constraints = []

        for k, v in _vars.items():
            costs += lpSum([salaries[k][i] * _vars[k][i] for i in v])
            rewards += lpSum([points[k][i] * _vars[k][i] for i in v])
            own_constraints += lpSum([owns[k][i] * _vars[k][i] for i in v])
            ceil_constraints += [ceilings[k][i] * _vars[k][i] for i in v]
            prob += lpSum([_vars[k][i] for i in v]) == pos_num_available[k]

        prob += lpSum(rewards)
        prob += lpSum(costs) <= SALARY_CAP
        prob += lpSum(own_constraints) <= OWN_CEILING
        prob += lpSum(ceil_constraints) >= CEIL_FLOOR

        # Solve LP problem
        prob.solve()

        # Collect solution results with additional details
        solution = {}
        totals = {
            "score": 0,
            "cost": 0,
            "ownership": 0,
            "ceiling": 0
        }
        
        
        for v in prob.variables():
            if v.varValue != 0:
                 # Extract the position and player name from the variable name
                pos_name = v.name.split("_")
                position = pos_name[0]  # The position, e.g., 'QB', 'RB', etc.
                
                 # The rest of the name is the player's name. Join the name back with spaces or underscores.
                player_name = "_".join(pos_name[1:])  # Player name parts joined by underscores

                # Debug: Check the available keys in the dictionaries
                print(f"Looking for Player: {player_name}")
                print(f"Available Players in Points[{position}]: {list(points[position].keys())}")
        

                
                # Calculate score, cost, ownership, and ceiling based on the player name
                try:
                    player_score = points[position][player_name] * v.varValue
                    player_cost = salaries[position][player_name] * v.varValue
                    player_ownership = owns[position][player_name] * v.varValue
                    player_ceiling = ceilings[position][player_name] * v.varValue
                except KeyError as e:
                    print(f"Error: Player {player_name} not found in {position}")
                    continue # Skip and move onto the next player

                solution[player_name] = {
                    "position": position,
                    "selected": v.varValue,
                    "score": player_score,
                    "constraints": {
                        "cost": salaries[position][player_name] * v.varValue,
                        "ownership": owns[position][player_name] * v.varValue,
                        "ceiling": ceilings[position][player_name] * v.varValue
                    }
                }

                # Update totals
                totals["score"] += player_score
                totals["cost"] += player_cost
                totals["ownership"] += player_ownership
                totals["ceiling"] += player_ceiling

        return render_template('index.html', solution=solution)

    # Initial page load
    return render_template('index.html', solution={})

if __name__ == '__main__':
    app.run(debug=True)
