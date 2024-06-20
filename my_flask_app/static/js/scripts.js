document.addEventListener('DOMContentLoaded', function () {
        const chartSelector = document.getElementById('chartSelector');
        const dateFilters = document.getElementById('dateFilters');
        const categoryFilters = document.getElementById('categoryFilters');
        const regionFilters = document.getElementById('regionFilters');
        const stateSelector = document.getElementById('stateSelector');
        const filterButton = document.getElementById('filterButton');
        const chartContainer = document.getElementById('chart');
        const loadingSpinner = document.getElementById('loadingSpinner');
        const colorPalette = ['#2E86C1', '#28B463', '#E74C3C', '#F1C40F', '#9B59B6', '#F39C12', '#1ABC9C', '#D35400', '#7D3C98', '#34495E'];


        function showLoading() {
            loadingSpinner.style.display = 'block';
        }

        function hideLoading() {
            loadingSpinner.style.display = 'none';
        }

        function showTooltip(x, y, value) {
            const tooltip = document.createElement('div');
            tooltip.classList.add('chart-tooltip');
            tooltip.style.left = `${x}px`;
            tooltip.style.top = `${y}px`;
            tooltip.innerText = value;
            chartContainer.appendChild(tooltip);
            setTimeout(() => {
                tooltip.style.opacity = 1;
            }, 0);
        }

        function hideTooltip() {
            const tooltips = document.querySelectorAll('.chart-tooltip');
            tooltips.forEach(tooltip => {
                tooltip.style.opacity = 0;
                setTimeout(() => {
                    tooltip.remove();
                }, 300);
            });
        }

        // Populate state selector dynamically
        fetch('/states')
            .then(response => response.json())
            .then(states => {
                const stateSelector = document.getElementById('stateSelector');
                states.forEach(state => {
                    const option = document.createElement('option');
                    option.value = state;
                    option.innerText = state;
                    stateSelector.appendChild(option);
                });
            });


        function renderChart(chartData, chartLabels, chartType, title) {
            const chartContainer = document.getElementById('chart');
            const chart = echarts.init(chartContainer);

            let option;
            if (chartType === 'bar') {
                option = {
                    color: colorPalette, title: {text: title}, tooltip: {
                        trigger: 'axis', axisPointer: {type: 'shadow'}, formatter: function (params) {
                            return `${params[0].name}: ${params[0].value}`;
                        }
                    }, xAxis: {
                        type: 'category', data: chartLabels, axisLabel: {interval: 0, rotate: 30}
                    }, yAxis: {type: 'value'}, series: [{
                        name: title, type: chartType, data: chartData, emphasis: {itemStyle: {color: 'green'}}
                    }], toolbox: {
                        feature: {
                            dataView: {readOnly: false}, restore: {}, saveAsImage: {}
                        }
                    }

                };
            } else if (chartType === 'line') {
                option = {
                    title: {
                        text: title,
                        left: 'center',
                        textStyle: {
                            fontSize: 18,
                            fontWeight: 'bold'
                        }
                    },
                    color: ['#007bff', '#ff7f50', '#87cefa', '#da70d6', '#32cd32', '#6495ed', '#ff69b4', '#ba55d3', '#cd5c5c', '#ffa500'],
                    tooltip: {
                        trigger: 'axis'
                    },
                    xAxis: {
                        type: 'category',
                        boundaryGap: false,
                        data: chartLabels
                    },
                    yAxis: {
                        type: 'value'
                    },
                    series: [{
                        name: title,
                        type: 'line',
                        data: chartData,
                        markPoint: {
                            data: [
                                {type: 'max', name: 'Max'},
                                {type: 'min', name: 'Min'}
                            ]
                        },
                        markLine: {
                            data: [
                                {type: 'average', name: 'Average'}
                            ]
                        }
                    }],
                    toolbox: {
                        feature: {
                            dataView: {readOnly: false},
                            restore: {},
                            saveAsImage: {}
                        }
                    }
                }
            }

            chart.on('click', function (params) {
                if (document.querySelector('.drill-down-button')) {
                    document.querySelector('.drill-down-button').remove();
                }
                const button = document.createElement('button');
                button.classList.add('drill-down-button');
                button.innerText = 'Drill Down';
                button.onclick = function () {

                    let chartType = '';
                    let fetchEndpoint = '';
                    let fetchParameterName = '';
                    let chartXAxisLabel = '';
                    // Determine the type of drill-down based on the chart that was clicked
                    if (params.seriesName === 'Customer Distribution by Region') {
                        chartType = 'bar';
                        fetchEndpoint = '/drilldown_city';
                        fetchParameterName = 'state';
                        chartXAxisLabel = 'Stores Distribution - ';
                    } else if (params.seriesName === 'Total Sales by Product Category') {
                        chartType = 'bar';
                        fetchEndpoint = '/drilldown';
                        fetchParameterName = 'category';
                        chartXAxisLabel = 'Drill Down - ';
                    }
                    // Fetch and render the drill-down data
                    if (fetchEndpoint) {
                        showLoading();
                        const fetchParameterValue = params.name;
                        fetch(`${fetchEndpoint}?${fetchParameterName}=${fetchParameterValue}`)
                            .then(response => response.json())
                            .then(data => {
                                const drillDownLabels = data.map(item => item[0]);
                                const drillDownData = data.map(item => item[1]);
                                renderChart(drillDownData, drillDownLabels, chartType, `${chartXAxisLabel}${fetchParameterValue}`);
                                hideLoading();
                                exitDrilldownButton.style.display = 'block';
                            });
                    }
                };
                chartContainer.appendChild(button);
            });

            window.addEventListener('resize', function () {
                chart.resize();
            });

            chart.setOption(option);
        }

        function updateChart() {
            showLoading();
            const selectedChart = chartSelector.value;
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            const category = document.getElementById('categorySelector').value;
            const region = document.getElementById('regionSelector').value;
            const state = document.getElementById('stateSelector').value;
            fetch(`/filter?chart=${selectedChart}&startDate=${startDate}&endDate=${endDate}&category=${category}&region=${region}&state=${state}`)
                .then(response => response.json())
                .then(data => {
                    let chartLabels, chartData, chartType, title;

                    switch (selectedChart) {
                        case 'total_sales_by_category':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'bar';
                            title = 'Total Sales by Product Category';
                            break;
                        case 'sales_trends_over_time':
                            chartLabels = data.map(item => item[0] + '-' + item[1]);
                            chartData = data.map(item => item[2]);
                            chartType = 'line';
                            title = 'Sales Trends Over Time';
                            break;
                        case 'top_selling_products':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'bar';
                            title = 'Top Selling Products';
                            break;
                        case 'customer_distribution':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'bar';
                            title = 'Customer Distribution by Region';
                            break;
                        case 'average_order_value':
                            chartLabels = ['Average Order Value'];
                            chartData = [data[0][0]];
                            chartType = 'bar';
                            title = 'Average Order Value';
                            break;
                        case 'customer_growth':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'line';
                            title = 'Customer Growth';
                            break;
                        default:
                            chartLabels = [];
                            chartData = [];
                            chartType = 'bar';
                            title = 'Chart';
                    }


                    renderChart(chartData, chartLabels, chartType, title);
                    hideLoading();
                });
        }

        document.addEventListener('DOMContentLoaded', function () {
            function captureChartAsImage() {
                const chartContainer = document.getElementById('chart');
                return html2canvas(chartContainer).then(canvas => {
                    return canvas.toDataURL('image/png');
                });
            }

            window.downloadChartAsPDF = function (chartName) {
                captureChartAsImage().then(imageData => {
                    fetch(`/download_chart_pdf`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            chart: chartName,
                            image: imageData
                        })
                    })
                        .then(response => {
                            if (!response.ok) {
                                throw new Error('Network response was not ok ' + response.statusText);
                            }
                            return response.blob();
                        })
                        .then(blob => {
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.style.display = 'none';
                            a.href = url;
                            a.download = `${chartName}.pdf`;
                            document.body.appendChild(a);
                            a.click();
                            window.URL.revokeObjectURL(url);
                        })
                        .catch(error => console.error('Error downloading PDF:', error));
                });
            }

            document.getElementById('downloadPdfButton').addEventListener('click', function () {
                const chartName = document.getElementById('chartSelector').value;
                window.downloadChartAsPDF(chartName);
            });
        });

// Initialize and handle exit drill-down functionality
        const exitDrilldownButton = document.createElement('button');
        exitDrilldownButton.classList.add('exit-drill-down-button');
        exitDrilldownButton.innerText = 'Exit Drill Down';
        exitDrilldownButton.style.display = 'none';
        exitDrilldownButton.addEventListener('click', function () {
            exitDrilldownButton.style.display = 'none';
            updateChart();
        });
        document.body.appendChild(exitDrilldownButton);
        document.addEventListener('DOMContentLoaded', function () {
            const downloadPdfButton = document.getElementById('downloadPdfButton');

            downloadPdfButton.addEventListener('click', function () {
                const selectedChart = chartSelector.value;
                fetch(`/download_chart_pdf?chart=${selectedChart}`)
                    .then(response => response.blob())
                    .then(blob => {
                        const url = window.URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.style.display = 'none';
                        a.href = url;
                        a.download = `${selectedChart}.pdf`;
                        document.body.appendChild(a);
                        a.click();
                        window.URL.revokeObjectURL(url);
                    })
                    .catch(error => console.error('Error downloading PDF:', error));
            });
        });


        function updateFilters() {
            const selectedOption = chartSelector.options[chartSelector.selectedIndex];
            const filters = selectedOption.dataset.filters.split(' ');

            dateFilters.style.display = filters.includes('date') ? 'block' : 'none';
            categoryFilters.style.display = filters.includes('category') ? 'block' : 'none';
            regionFilters.style.display = filters.includes('region') ? 'block' : 'none';
            stateSelector.style.display = filters.length > 0 ? 'block' : 'none';
        }

        chartSelector.addEventListener('change', updateFilters);
        filterButton.addEventListener('click', updateChart);

// Perform initial chart update to render default chart
        updateFilters();
    }
)
;
