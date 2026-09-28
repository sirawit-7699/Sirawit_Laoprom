(() => {
  const node = document.getElementById('chart-data');
  if (!node) return;
  const plot = JSON.parse(node.textContent);
  if (typeof Chart === 'undefined') {
    document.querySelectorAll('.chart-wrap').forEach(el => {
      el.textContent = 'โหลดกราฟไม่สำเร็จ กรุณาตรวจสอบอินเทอร์เน็ตแล้วรีเฟรชหน้า';
    });
    return;
  }
  const theme = getComputedStyle(document.documentElement);
  const color = name => theme.getPropertyValue(name).trim();
  const sources = {
    sensor: {label: 'เซนเซอร์อาคาร 7', point: 'circle', dash: []},
    forecast: {label: 'พยากรณ์กรมอุตุฯ', point: 'rectRot', dash: [6, 3]}
  };
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.color = color('--muted');
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const charts = [];
  const initialMotion = document.documentElement.classList.contains('page-enter');
  motion.addEventListener('change', () => {
    if (motion.matches) charts.forEach(chart => {
      chart.stop();
      chart.options.animation = false;
      chart.update('none');
    });
  });

  function draw(canvas, sets, label, animate = initialMotion) {
    const comparisonKey = canvas.dataset.compare;
    const format = value => Number.isFinite(value)
      ? value.toLocaleString('th-TH', {maximumFractionDigits: 2}) : '—';
    const graph = new Chart(canvas, {
      type: 'line',
      data: {labels: plot.labels, datasets: sets},
      options: {
        responsive: true, maintainAspectRatio: false,
        animation: motion.matches || !animate ? false : {duration: 450, easing: 'easeOutQuart'},
        transitions: {active: {animation: {duration: 0}}, resize: {animation: {duration: 0}}},
        interaction: {mode: 'index', intersect: false},
        plugins: {
          legend: {display: true, position: 'bottom', labels: {
            usePointStyle: true, boxWidth: 9, padding: 18,
            color: color('--ink'), font: {size: 12}
          }},
          tooltip: {
            backgroundColor: color('--nav'), titleColor: color('--surface'),
            bodyColor: color('--surface'), borderColor: color('--accent'), borderWidth: 1,
            padding: 12, cornerRadius: 8, bodySpacing: 6, usePointStyle: true,
            callbacks: {title: items => items.length ? items[0].label : '',
              label: item => comparisonKey ? '' : `${item.dataset.label}: ${item.formattedValue}`,
              beforeBody: items => {
                if (!comparisonKey || !items.length) return [];
                const i = items[0].dataIndex;
                const sensor = plot.series[comparisonKey][i];
                const forecast = plot.series['tmd_' + comparisonKey][i];
                const difference = Number.isFinite(sensor) && Number.isFinite(forecast)
                  ? Math.abs(sensor - forecast) : null;
                return [`Sensor: ${format(sensor)}`, `TMD Forecast: ${format(forecast)}`,
                  `ผลต่าง: ${format(difference)}`];
              },
              afterBody: () => label}
          }
        },
        scales: {
          x: {grid: {display: false}, ticks: {maxTicksLimit: window.innerWidth < 600 ? 3 : 6, maxRotation: 0}},
          y: {title: {display: true, text: label}, grid: {color: color('--line-soft')}}
        }
      }
    });
    charts.push(graph);
    return graph;
  }
  function series(key, source) {
    const style = sources[source];
    const variable = key.replace(/^tmd_/, '');
    const seriesColor = color(`--chart-${variable}-${source}`);
    return {
      label: style.label, data: plot.series[key],
      borderColor: seriesColor, backgroundColor: seriesColor,
      borderDash: style.dash, borderWidth: 2.5,
      pointStyle: style.point, pointBackgroundColor: color('--surface'),
      pointBorderColor: seriesColor, pointBorderWidth: 2,
      pointRadius: plot.labels.length > 60 ? 1.5 : 3.5,
      pointHoverRadius: 6, pointHitRadius: 10,
      fill: false, tension: 0.2, spanGaps: false
    };
  }
  const trend = document.getElementById('trendChart');
  const select = document.getElementById('metric');
  if (trend && select) {
    const source = window.location.pathname === '/tmd' ? 'forecast' : 'sensor';
    let graph;
    const update = () => {
      trend.closest('.card-soft').dataset.variable = select.value;
      if (graph) {
        charts.splice(charts.indexOf(graph), 1);
        graph.destroy();
        graph = draw(trend, [series(select.value, source)], select.selectedOptions[0].text, true);
      } else {
        graph = draw(trend, [series(select.value, source)], select.selectedOptions[0].text);
      }
    };
    select.addEventListener('change', update);
    update();
  }
  document.querySelectorAll('[data-compare]').forEach(canvas => {
    const key = canvas.dataset.compare;
    canvas.closest('.card-soft').dataset.variable = key;
    draw(canvas, [series(key, 'sensor'), series('tmd_' + key, 'forecast')], canvas.dataset.label);
  });
})();
