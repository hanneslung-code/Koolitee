(() => {
  const regionSelect = document.getElementById('region');
  const areaSelect = document.getElementById('area');
  if (!regionSelect || !areaSelect) return;

  let regions = {};
  try { regions = JSON.parse(regionSelect.dataset.areas || '{}'); } catch (_) { regions = {}; }
  const selectedArea = areaSelect.dataset.selected || '';
  const schoolSelect = document.getElementById('school');
  const otherSchoolWrap = document.getElementById('other-school-wrap');
  const otherSchoolInput = document.getElementById('other_school');
  function updateOtherSchool() {
    if (!schoolSelect || !otherSchoolWrap) return;
    const show = schoolSelect.value === '__other__';
    otherSchoolWrap.hidden = !show;
    if (otherSchoolInput) otherSchoolInput.required = show;
  }
  if (schoolSelect) { schoolSelect.addEventListener('change', updateOtherSchool); updateOtherSchool(); }

  function updateAreas(keepSelected = false) {
    const wanted = keepSelected ? (areaSelect.value || selectedArea) : '';
    const list = regions[regionSelect.value] || [];
    areaSelect.replaceChildren();
    const first = document.createElement('option');
    first.value = '';
    first.textContent = list.length ? 'Vali asum / asula…' : 'Vali esmalt piirkond…';
    areaSelect.append(first);
    list.forEach(name => {
      const option = document.createElement('option');
      option.value = name;
      option.textContent = name;
      if (name === wanted) option.selected = true;
      areaSelect.append(option);
    });
    areaSelect.disabled = list.length === 0;
  }
  regionSelect.addEventListener('change', () => updateAreas(false));
  updateAreas(true);
})();
