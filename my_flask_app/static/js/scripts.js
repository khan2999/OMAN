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
                color: colorPalette,
                title: { text: title },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'shadow' },
                    formatter: function (params) {
                        return `${params[0].name}: ${params[0].value.toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        })}`;
                    }
                },
                xAxis: {
                    type: 'category',
                    data: chartLabels,
                    axisLabel: { interval: 0 }
                },
                yAxis: {
                    type: 'value',
                    axisLabel: {
                        show: true,
                        fontSize: 10,
                        color: '#333',
                        rotate: 0,
                        formatter: '{value}'
                    }
                },
                series: [{
                    name: title,
                    type: chartType,
                    data: chartData,
                    emphasis: { itemStyle: { color: 'green' } }
                }],
                toolbox: {
                    feature: {
                        dataView: { readOnly: false },
                        restore: {},
                        saveAsImage: {},
                        dataZoom: {}, // Added data zoom
                        magicType: { type: ['line', 'bar'] } // Added toggle between line and bar chart
                    }
                },
                dataZoom: [
                    { type: 'slider', start: 0, end: 100 },
                    { type: 'inside', start: 0, end: 100 }
                ] // Added data zoom slider and inside zoom
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
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross'
                    },
                    formatter: function (params) {
                        return `${params[0].name}: ${params[0].value.toLocaleString('en-US', {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        }).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
                    }
                },
                xAxis: {
                    type: 'category',
                    boundaryGap: false,
                    data: chartLabels,
                    axisLabel: { interval: 0, rotate: 30 }
                },
                yAxis: {
                    type: 'value',
                    axisLabel: {
                        formatter: function (value) {
                            return value.toLocaleString('en-US');
                        }
                    }
                },
                series: [{
                    name: title,
                    type: 'line',
                    data: chartData,
                    markPoint: {
                        data: [
                            { type: 'max', name: 'Max' },
                            { type: 'min', name: 'Min' }
                        ]
                    },
                    markLine: {
                        data: [
                            { type: 'average', name: 'Average' }
                        ]
                    }
                }],
                toolbox: {
                    feature: {
                        dataView: { readOnly: false },
                        restore: {},
                        saveAsImage: {},
                        dataZoom: {}, // Added data zoom
                        magicType: { type: ['line', 'bar'] } // Added toggle between line and bar chart
                    }
                },
                dataZoom: [
                    { type: 'slider', start: 0, end: 100 },
                    { type: 'inside', start: 0, end: 100 }
                ] // Added data zoom slider and inside zoom
            }
        }

        chart.on('click', function (params) {
            // Determine if drill-down button should be shown
            const drillDownCharts = ['Total Sales by Product Category', 'Top Selling Products'];
            if (!drillDownCharts.includes(title)) {
                return;
            }

            if (document.querySelector('.drill-down-button')) {
                document.querySelector('.drill-down-button').remove();
            }
            const button = document.createElement('button');
            button.classList.add('drill-down-button');
            button.innerText = 'Drill Down';
            button.onclick = async function () {
                let fetchUrl;
                if (title === 'Total Sales by Product Category') {
                    fetchUrl = `/drilldown?category=${params.name}`;
                } else if (title === 'Top Selling Products') {
                    fetchUrl = `/drilldown?product_name=${params.name}`;
                } else {
                    return;
                }
                try {
                    showLoading();
                    const response = await fetch(fetchUrl);
                    if (!response.ok) {
                        throw new Error(`Error fetching drill-down data: ${response.status} ${response.statusText}`);
                    }
                    const data = await response.json();
                    const drillDownLabels = data.map(item => item[0]);
                    const drillDownData = data.map(item => item[1]);
                    renderChart(drillDownData, drillDownLabels, 'bar', `Drill Down - ${params.name}`);
                    hideLoading();
                    exitDrilldownButton.style.display = 'block';
                } catch (error) {
                    console.error('Error fetching drill-down data:', error);
                    hideLoading();
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
        let category = document.getElementById('categorySelector').value;
        const region = document.getElementById('regionSelector').value;
        const state = document.getElementById('stateSelector').value;
        if (category === "Pizza") {
            category = "";
        }
        fetch(`/filter?chart=${selectedChart}&startDate=${startDate}&endDate=${endDate}&category=${category}&region=${region}&state=${state}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    hideLoading();
                    return;
                }
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
                    case 'product_details':
                        chartLabels = data.map(item => item[0]);
                        chartData = data.map(item => item[2]);
                        chartType = 'bar';
                        title = 'Product Details (Price by SKU)';
                        break;
                    default:
                        chartLabels = [];
                        chartData = [];
                        chartType = 'bar';
                        title = '';
                }

                renderChart(chartData, chartLabels, chartType, title);
                hideLoading();

                // Show/Hide Drill Down and Exit Drill Down buttons based on selected chart
                const drillDownCharts = ['total_sales_by_category', 'top_selling_products'];
                const drillDownButton = document.querySelector('.drill-down-button');
                if (drillDownCharts.includes(selectedChart)) {
                    if (!drillDownButton) {
                        const button = document.createElement('button');
                        button.classList.add('drill-down-button');
                        button.innerText = 'Drill Down';
                        chartContainer.appendChild(button);
                    }
                } else {
                    if (drillDownButton) {
                        drillDownButton.remove();
                    }
                    exitDrilldownButton.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error fetching chart data:', error);
                hideLoading();
            });
    }

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

    // Initialize and handle exit drill-down functionality
    const exitDrilldownButton = document.createElement('button');
    exitDrilldownButton.classList.add('exit-drill-down-button');
    exitDrilldownButton.innerText = 'Exit Drill Down';
    exitDrilldownButton.style.display = 'none';
    exitDrilldownButton.addEventListener('click', function () {
        exitDrilldownButton.style.display = 'none';
        updateChart();
    });
    chartContainer.appendChild(exitDrilldownButton);

    // Perform initial chart update to render default chart
    updateFilters();
});
