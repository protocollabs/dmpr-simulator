# Dynamic MultiPath Routing Protocol - Simulator

## What is the DMPR Simulator?

dmpr-simulator allows you to define topologies and on top of that scenarios to
simulate different use cases of DMPR.

Features:

* static and moving routers
* disappearing and reappearing nodes
* multiple interfaces, policies and more
* generate visualizations of each step

### Demonstration video
[![DMPR Promo Video](http://img.youtube.com/vi/PypxZ2UQi3E/0.jpg)](https://www.youtube.com/watch?v=PypxZ2UQi3E)

## Installation

This repository uses git submodules to include the DMPR core component. You need
to clone this repository recursively.

```
git clone --recursive https://github.com/protocollabs/dmpr-simulator.git
python3 -m venv venv
source venv/bin/activate
pip install -r requirements
```

For drawing the topologies and generating a movie, PIL, cairo python bindings
and ffmpeg are required.

```
sudo apt-get install python3-cairo-dev python3-pil
```

## Usage

The simulation is structured into different tiers. First of all, there is the
core simulator. Building on this are different topologies like a interconnected
grid of nodes, a circle or a random distribution of nodes. On top of that are
predefined scenarios which run on or more topologies. To analyze the output
of scenarios, there are a few predefined analyze scripts, most of which are
tailored for one scenario.

## Extending DMPR Simulator

Take a look at the existing topologies and scenarios if you want to build your
own. A topology usually is class with the following API: 
- `Topology.__init__(**kwargs)`: The constructor get's all configuration options
- `Topology.prepare() -> List[Router]`: A prepare method builds initializes the
  topology and creates the routers. You can add, remove or modify routers in
  the returned list to if you have special requirements
- `Topology.start() -> Iterator`: The start method is an iterator which yields
  after every step to give you the option to modify the running simulation.


### Install Dependencies on Debian based Systems

```
sudo aptitude install python3-cairo-dev python3-pil
```



