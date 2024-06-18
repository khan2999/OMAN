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
                }
            } else if (chartType === 'line') {
                option = {
                    title: {text: title, left: 'center', textStyle: {fontSize: 18, fontWeight: 'bold'}},
                    tooltip: {trigger: 'axis'},
                    xAxis: {type: 'category', boundaryGap: false, data: chartLabels},
                    yAxis: {type: 'value'},
                    series: [{
                        name: title,
                        type: 'line',
                        data: chartData,
                        markPoint: {data: [{type: 'max', name: 'Max'}, {type: 'min', name: 'Min'}]},
                        markLine: {data: [{type: 'average', name: 'Average'}]}
                    }],
                    toolbox: {
                        feature: {
                            dataView: {readOnly: false},
                            restore: {},
                            saveAsImage: {}
                        }
                    }
                };
            } else if (chartType === 'bar' && title === 'Store Performance Comparison') {
                const ctx = document.getElementById('chart-container-3').getContext('2d');
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: chartLabels,
                        datasets: [{
                            label: 'Total Sales',
                            data: chartData.map(item => item.total_sales),
                            backgroundColor: 'green',
                            emphasis: {itemStyle: {color: 'green'}}
                        }, {
                            label: 'Number of Orders',
                            data: chartData.map(item => item.num_orders),
                            backgroundColor: 'blue',
                            emphasis: {itemStyle: {color: 'blue'}}
                        }, {
                            label: 'Average Order Size',
                            data: chartData.map(item => item.average_order_size),
                            backgroundColor: 'red',
                            emphasis: {itemStyle: {color: 'red'}}
                        }]
                    },
                    options: {
                        scales: {
                            yAxes: [{
                                ticks: {
                                    beginAtZero: true
                                }
                            }]
                        },
                        title: {
                            display: true,
                            text: 'Store Performance Comparison'
                        }
                    }
                });
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
                            chartType = 'gauge';
                            title = 'Average Order Value';
                            break;
                        case 'customer_growth':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'line';
                            title = 'Customer Growth';
                            break;

                        case 'sales_by_day_of_week':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'bar';
                            title = 'Sales by Day of Week';
                            break;
                        case 'store_performance_by_category':
                            const categories = [...new Set(data.map(item => item.category))];
                            const storeLabels = [...new Set(data.map(item => item.storeID))];
                            chartData = categories.map((category) => {
                                return {
                                    label: category,
                                    data: storeLabels.map(store => {
                                        const item = data.find(item => item.storeID === store && item.category === category);
                                        return item ? item.total_sales : 0;
                                    }),
                                    backgroundColor: colorPalette[categories.indexOf(category) % colorPalette.length],
                                };
                            });
                            chartLabels = storeLabels;
                            chartType = 'bar';
                            title = 'Store Performance by Category';
                            break;
                        case 'average_order_value_over_time':
                            chartLabels = data.map(item => item[0]);
                            chartData = data.map(item => item[1]);
                            chartType = 'line';
                            title = 'Average Order Value Over Time';
                            break;
                        case 'store_performance_comparison':
                            chartLabels = data.map(item => item.storeID);
                            chartData = data.map(item => ({
                                name: item.storeID,
                                total_sales: item.total_sales,
                                num_orders: item.num_orders,
                                average_order_size: item.average_order_size
                            }));
                            chartType = 'bar'; // Adjust chart type as per visualization needs
                            title = 'Store Performance Comparison';
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
