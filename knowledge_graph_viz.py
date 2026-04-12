#!/usr/bin/env python3
"""
Knowledge Graph Visualizer - Web-based Visualization

Generates interactive HTML visualization of the knowledge graph.
Uses D3.js for network visualization.

Usage:
    python3 knowledge_graph_viz.py
    # Opens: http://localhost:8080
"""

import json
import logging
import webbrowser
import threading
import time
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from knowledge_graph import KnowledgeGraph, get_knowledge_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeGraphViz:
    """Generate interactive visualization for knowledge graph."""

    def __init__(self):
        self.graph = get_knowledge_graph()
        self.output_dir = Path(__file__).parent / "viz"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(self) -> str:
        """Generate interactive HTML visualization."""

        # Get graph data
        nodes = []
        links = []

        for node_id, node in self.graph._nodes.items():
            nodes.append({
                'id': node.id,
                'label': f"{node.type}\n{node.source_bot}",
                'type': node.type,
                'bot': node.source_bot,
                'group': self._get_bot_group(node.source_bot)
            })

        for edge in self.graph._edges:
            links.append({
                'source': edge['from'],
                'target': edge['to'],
                'type': edge.get('type', 'related')
            })

        # Generate HTML
        html = self._generate_html_template(nodes, links)

        output_file = self.output_dir / 'knowledge_graph.html'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"Generated visualization: {output_file}")
        return str(output_file)

    def _get_bot_group(self, bot: str) -> int:
        """Get group ID for bot coloring."""
        bot_groups = {
            '编导': 1, '场控': 1, '运营': 1,  # Content group
            '剪辑': 2, '美工': 2,  # Creative group
            '客服': 3, '渠道': 3,  # Service group
            'system': 0
        }
        return bot_groups.get(bot, 99)

    def _generate_html_template(self, nodes: list, links: list) -> str:
        """Generate HTML template with D3.js visualization."""

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Phoenix Core 知识图谱可视化</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            overflow: hidden;
        }}
        .container {{
            display: flex;
            height: 100vh;
        }}
        .sidebar {{
            width: 300px;
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            padding: 20px;
            color: white;
            overflow-y: auto;
        }}
        .sidebar h2 {{
            margin-bottom: 20px;
            font-size: 1.5em;
            border-bottom: 2px solid #4fc3f7;
            padding-bottom: 10px;
        }}
        .stats {{
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
        }}
        .stats-item {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .stats-value {{
            font-weight: bold;
            color: #4fc3f7;
        }}
        .main {{
            flex: 1;
            position: relative;
        }}
        #graph {{
            width: 100%;
            height: 100%;
        }}
        .node {{
            cursor: pointer;
        }}
        .node circle {{
            stroke: #fff;
            stroke-width: 2px;
        }}
        .node text {{
            fill: white;
            font-size: 12px;
            text-shadow: 0 1px 4px rgba(0,0,0,0.8);
        }}
        .link {{
            stroke: rgba(255,255,255,0.3);
            stroke-width: 2px;
        }}
        .link.propagation {{
            stroke: #4fc3f7;
            stroke-dasharray: 5,5;
        }}
        .tooltip {{
            position: absolute;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 15px;
            border-radius: 8px;
            font-size: 14px;
            max-width: 300px;
            pointer-events: none;
            z-index: 1000;
            display: none;
        }}
        .legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 10px;
            color: white;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}
        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 10px;
        }}
        .controls {{
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }}
        .btn {{
            background: rgba(79,195,247,0.2);
            border: 1px solid #4fc3f7;
            color: white;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            transition: all 0.3s;
        }}
        .btn:hover {{
            background: rgba(79,195,247,0.4);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="sidebar">
            <h2>📊 知识图谱</h2>
            <div class="stats">
                <div class="stats-item">
                    <span>总节点数</span>
                    <span class="stats-value" id="node-count">{len(nodes)}</span>
                </div>
                <div class="stats-item">
                    <span>总连接数</span>
                    <span class="stats-value" id="link-count">{len(links)}</span>
                </div>
                <div class="stats-item">
                    <span>Bot 数量</span>
                    <span class="stats-value" id="bot-count">{len(set(n['bot'] for n in nodes))}</span>
                </div>
            </div>
            <div id="node-details">
                <p>点击节点查看详情</p>
            </div>
        </div>
        <div class="main">
            <div id="graph"></div>
            <div class="controls">
                <button class="btn" onclick="resetZoom()">🔍 重置视图</button>
                <button class="btn" onclick="toggleLabels()">🏷️ 切换标签</button>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color" style="background: #e57373;"></div>
                    <span>Content (编导/场控/运营)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #81c784;"></div>
                    <span>Creative (剪辑/美工)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #64b5f6;"></div>
                    <span>Service (客服/渠道)</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #ba68c8;"></div>
                    <span>System</span>
                </div>
            </div>
        </div>
    </div>
    <div class="tooltip" id="tooltip"></div>

    <script>
        // Graph data
        const graphData = {{
            nodes: {json.dumps(nodes)},
            links: {json.dumps(links)}
        }};

        // Color scale
        const colorScale = d3.scaleOrdinal()
            .domain([0, 1, 2, 3, 99])
            .range(['#ba68c8', '#e57373', '#81c784', '#64b5f6', '#ffb74d']);

        // Create SVG
        const width = window.innerWidth - 300;
        const height = window.innerHeight;

        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", width)
            .attr("height", height);

        // Zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});

        svg.call(zoom);

        const g = svg.append("g");

        // Force simulation
        const simulation = d3.forceSimulation()
            .force("link", d3.forceLink().id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(30));

        // Draw links
        const link = g.append("g")
            .selectAll("line")
            .data(graphData.links)
            .join("line")
            .attr("class", d => "link " + (d.type === 'propagation' ? 'propagation' : ''))
            .attr("stroke", d => d.type === 'propagation' ? '#4fc3f7' : 'rgba(255,255,255,0.3)');

        // Draw nodes
        const node = g.append("g")
            .selectAll("g")
            .data(graphData.nodes)
            .join("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Node circles
        node.append("circle")
            .attr("r", 20)
            .attr("fill", d => colorScale(d.group));

        // Node labels
        node.append("text")
            .attr("dy", 35)
            .attr("text-anchor", "middle")
            .text(d => d.type);

        // Tooltip
        const tooltip = d3.select("#tooltip");

        node.on("mouseover", (event, d) => {{
            tooltip
                .style("display", "block")
                .html(`
                    <strong>${{d.id}}</strong><br/>
                    类型：${{d.type}}<br/>
                    Bot: ${{d.bot}}<br/>
                    组别：${{d.group}}
                `);
        }})
        .on("mousemove", (event) => {{
            tooltip
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px");
        }})
        .on("mouseout", () => {{
            tooltip.style("display", "none");
        }})
        .on("click", (event, d) => {{
            showNodeDetails(d);
        }});

        // Simulation tick
        simulation.nodes(graphData.nodes).on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

        simulation.force("link").links(graphData.links);

        // Drag functions
        function dragstarted(event, d) {{
            simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}

        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}

        function dragended(event, d) {{
            simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}

        // Show node details
        function showNodeDetails(d) {{
            const details = document.getElementById('node-details');
            details.innerHTML = `
                <h3>${{d.id}}</h3>
                <p><strong>类型:</strong> ${{d.type}}</p>
                <p><strong>Bot:</strong> ${{d.bot}}</p>
                <p><strong>组别:</strong> ${{d.group}}</p>
            `;
        }}

        // Controls
        function resetZoom() {{
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }}

        let labelsVisible = true;
        function toggleLabels() {{
            labelsVisible = !labelsVisible;
            node.select("text").style("display", labelsVisible ? "block" : "none");
        }}
    </script>
</body>
</html>
"""

    def start_server(self, port: int = 8080):
        """Start local web server."""
        handler = SimpleHTTPRequestHandler

        class CustomHandler(handler):
            def do_GET(self):
                if self.path == '/' or self.path == '/index.html':
                    self.path = str(self.output_dir / 'knowledge_graph.html')
                return super().do_GET()

        server = HTTPServer(('localhost', port), CustomHandler)
        logger.info(f"Starting server at http://localhost:{port}")

        def run():
            server.serve_forever()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        # Open browser
        time.sleep(1)
        webbrowser.open(f'http://localhost:{port}')
        logger.info("Browser opened. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()
            logger.info("Server stopped")


def main():
    """Main entry point."""
    viz = KnowledgeGraphViz()

    # Generate HTML
    html_file = viz.generate_html()

    # Ask if user wants to open browser
    print(f"\n已生成可视化文件：{html_file}")
    print("\n选项:")
    print("1. 在浏览器中打开 (http://localhost:8080)")
    print("2. 直接打开 HTML 文件")
    print("3. 退出")

    choice = input("\n请选择 (1/2/3): ")

    if choice == '1':
        viz.start_server(port=8080)
    elif choice == '2':
        webbrowser.open(f'file://{html_file}')
        print("已打开 HTML 文件")
    else:
        print("退出")


if __name__ == "__main__":
    main()
