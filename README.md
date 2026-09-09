# Grid Analyser

A multi-node power grid fault detection system built for the Ghanaian electricity grid context, combining a desktop GUI with machine learning-based anomaly detection.

## Overview

Grid Analyser simulates and monitors multiple grid nodes, using an Isolation Forest anomaly detection model to flag potential faults in real time. It's built as a learning project under [Boundcraft](#), with an eye toward eventually decoupling the detection engine into a containerized, distributed service.

## Features

- **Multi-node simulation** — models several substation-like nodes and their electrical parameters
- **Fault detection** — uses scikit-learn's `IsolationForest` to flag anomalous readings
- **Desktop GUI** — built with Tkinter for live monitoring and visualization
- **Persistent storage** — SQLite backend for historical readings and detected events

## Architecture

The project is organized into 7 core modules, separating:
- Data generation / ingestion
- The anomaly detection engine
- Database access (SQLite)
- The Tkinter GUI layer
- Supporting utilities and configuration

## Tech Stack

- **Language:** Python
- **GUI:** Tkinter
- **ML:** scikit-learn (Isolation Forest)
- **Database:** SQLite

## Getting Started

### Prerequisites

- Python 3.x
- pip

### Installation

```bash
git clone https://github.com/<your-username>/grid-analyser.git
cd grid-analyser
pip install -r requirements.txt
```

### Usage

```bash
python main.py
```

> Update the entry-point filename above to match your actual main script.

## Roadmap

- [ ] Line-by-line code review and cleanup
- [ ] Decouple the fault-detection engine from the Tkinter GUI into a standalone service
- [ ] Containerize the detection engine
- [ ] Deploy across a local multi-node `kind` Kubernetes cluster (provisioned via Terraform) to simulate distributed substation nodes
- [ ] Add a resilience / self-healing demo

## License

Add a license of your choice (MIT is a common default for portfolio projects).

## Author

Built by Cami, part of the [Boundcraft](#) project ecosystem.
