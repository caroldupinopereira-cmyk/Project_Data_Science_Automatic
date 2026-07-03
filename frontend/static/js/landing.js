(function () {
  'use strict';

  /* ═══════════════════════════════════════════════════════
     THREE.JS — 5 SCENE MANAGER
     ═══════════════════════════════════════════════════════ */

  const SCENE_NAMES = [
    'Bar Chart 3D',
    'Scatter Plot 3D',
    'Wave Chart 3D',
    'Heatmap Grid 3D',
    'Distribution Curve 3D',
  ];

  const SCENE_DURATION = 4500;
  const FADE_DURATION = 600;
  const isMobile = window.innerWidth < 768;
  const particleCount = isMobile ? 300 : 600;

  let renderer, camera, mainScene;
  let sceneGroup = new THREE.Group();
  let currentSceneIndex = 0;
  let sceneOpacity = 1;
  let transitionPhase = 'none';
  let sceneClock = new THREE.Clock();
  let sceneTimer = 0;
  let animFrameId = null;
  let sceneTime = 0;
  let transitionProgress = 0;

  // ── Robot ──
  let robots = [];
  let robotMixers = [];
  let robotParticleGeo = null;
  let robotParticles = null;
  let robotParticleVel = [];
  let robotAccentLight = null;

  const CAMERA_POSITIONS = [
    { x: 0, y: 10, z: 22 },
    { x: 0, y: 5, z: 18 },
    { x: 0, y: 14, z: 20 },
    { x: 0, y: 18, z: 18 },
    { x: 0, y: 4, z: 22 },
  ];

  let cameraTarget = new THREE.Vector3(0, 10, 22);
  let cameraCurrent = new THREE.Vector3(0, 10, 22);

  /* ── Scene Data ── */
  let sceneData = {};

  function disposeObject(obj) {
    if (!obj) return;
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) {
      if (Array.isArray(obj.material)) {
        obj.material.forEach(function (m) { m.dispose(); });
      } else {
        obj.material.dispose();
      }
    }
    if (obj.children) {
      while (obj.children.length > 0) {
        disposeObject(obj.children[0]);
        obj.remove(obj.children[0]);
      }
    }
  }

  function buildScene(index, time) {
    const group = new THREE.Group();
    group.name = 'scene-' + index;
    group.opacity = 0;

    switch (index) {
      case 0: buildBarChart(group, time); break;
      case 1: buildScatterPlot(group, time); break;
      case 2: buildWaveChart(group, time); break;
      case 3: buildHeatmap(group, time); break;
      case 4: buildDistributionCurve(group, time); break;
    }

    return group;
  }

  /* ── Scene 1: Bar Chart 3D ── */
  function buildBarChart(group, time) {
    const rows = 5, cols = 6;
    const spacing = 1.8;
    const startX = -(cols - 1) * spacing * 0.5;
    const startZ = -(rows - 1) * spacing * 0.5;
    const bars = [];

    const pointLight = new THREE.PointLight(0x2563eb, 1, 30);
    pointLight.position.set(0, 12, 0);
    group.add(pointLight);

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const height = 1 + Math.random() * 7;
        const t = height / 8;
        const color = new THREE.Color().setHSL(0.58 + t * 0.12, 0.8, 0.3 + t * 0.4);
        const geo = new THREE.BoxGeometry(0.9, height, 0.9);
        const mat = new THREE.MeshPhongMaterial({
          color: color,
          emissive: color,
          emissiveIntensity: 0.08,
          shininess: 40,
        });
        const mesh = new THREE.Mesh(geo, mat);
        const x = startX + c * spacing;
        const z = startZ + r * spacing;
        mesh.position.set(x, height * 0.5 - 3, z);
        mesh.castShadow = true;
        group.add(mesh);

        const edges = new THREE.EdgesGeometry(geo);
        const edgeMat = new THREE.LineBasicMaterial({
          color: 0x3b82f6,
          transparent: true,
          opacity: 0.15,
        });
        const line = new THREE.LineSegments(edges, edgeMat);
        line.position.copy(mesh.position);
        group.add(line);

        bars.push({
          mesh: mesh,
          line: line,
          baseHeight: height,
          offset: Math.random() * Math.PI * 2,
          speed: 0.5 + Math.random() * 0.8,
          px: x,
          pz: z,
        });
      }
    }

    sceneData.bars = bars;
  }

  /* ── Scene 2: Scatter Plot 3D ── */
  function buildScatterPlot(group, time) {
    const clusterCenters = [
      { x: -4, y: 0, z: -3, color: 0xf472b6 },
      { x: 4, y: 0, z: -3, color: 0x60a5fa },
      { x: -4, y: 0, z: 3, color: 0x34d399 },
      { x: 4, y: 0, z: 3, color: 0xfbbf24 },
      { x: 0, y: 2, z: 0, color: 0xa78bfa },
    ];

    const positions = [];
    const colors = [];

    for (let i = 0; i < 800; i++) {
      const cluster = clusterCenters[Math.floor(Math.random() * clusterCenters.length)];
      const px = cluster.x + gaussRandom() * 1.2;
      const py = cluster.y + gaussRandom() * 1.2;
      const pz = cluster.z + gaussRandom() * 1.2;
      positions.push(px, py, pz);

      const col = new THREE.Color(cluster.color);
      colors.push(col.r, col.g, col.b);
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));

    const mat = new THREE.PointsMaterial({
      size: 0.12,
      sizeAttenuation: true,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
    });

    const points = new THREE.Points(geo, mat);
    group.add(points);
    sceneData.scatterPoints = points;
    sceneData.scatterBasePos = positions.slice();

    /* Axis lines */
    const axisMat = new THREE.LineBasicMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.15,
    });
    for (let sign = -1; sign <= 1; sign += 2) {
      const pts = [
        new THREE.Vector3(-7 * sign, 0, 0),
        new THREE.Vector3(7 * sign, 0, 0),
      ];
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      group.add(new THREE.Line(g, axisMat.clone()));
    }
  }

  function gaussRandom() {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /* ── Scene 3: Wave / Line Chart 3D ── */
  function buildWaveChart(group, time) {
    const size = 40;
    const geo = new THREE.PlaneGeometry(size, size, size, size);
    geo.rotateX(-Math.PI * 0.5);
    const pos = geo.attributes.position.array;

    sceneData.wavePositions = pos;
    sceneData.waveGeo = geo;

    const wireMat = new THREE.MeshPhongMaterial({
      color: 0x1d4ed8,
      wireframe: true,
      transparent: true,
      opacity: 0.5,
    });
    const wireMesh = new THREE.Mesh(geo, wireMat);
    wireMesh.position.y = -3;
    group.add(wireMesh);

    const solidMat = new THREE.MeshPhongMaterial({
      color: 0x1d4ed8,
      transparent: true,
      opacity: 0.15,
      side: THREE.DoubleSide,
    });
    const solidMesh = new THREE.Mesh(geo.clone(), solidMat);
    solidMesh.position.y = -3;
    group.add(solidMesh);

    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(0, 15, 10);
    group.add(dirLight);

    const ambLight = new THREE.AmbientLight(0x1a3a7a, 0.4);
    group.add(ambLight);

    /* Sweeping lines */
    const sweepGroup = new THREE.Group();
    const sweepMat = new THREE.LineBasicMaterial({
      color: 0x06b6d4,
      transparent: true,
      opacity: 0.3,
    });
    for (let i = 0; i < 5; i++) {
      const pts = [];
      for (let x = -size * 0.5; x <= size * 0.5; x += 0.5) {
        pts.push(new THREE.Vector3(x, 0, 0));
      }
      const g = new THREE.BufferGeometry().setFromPoints(pts);
      const line = new THREE.Line(g, sweepMat.clone());
      line.position.z = -size * 0.5 + (size / 6) * (i + 0.5);
      sweepGroup.add(line);
    }
    sweepGroup.position.y = 2;
    group.add(sweepGroup);
    sceneData.sweepGroup = sweepGroup;
  }

  /* ── Scene 4: Heatmap Grid 3D ── */
  function buildHeatmap(group, time) {
    const gridSize = 10;
    const spacing = 1.5;
    const startX = -(gridSize - 1) * spacing * 0.5;
    const startZ = -(gridSize - 1) * spacing * 0.5;
    const tiles = [];

    for (let r = 0; r < gridSize; r++) {
      for (let c = 0; c < gridSize; c++) {
        const val = Math.random();
        const geo = new THREE.BoxGeometry(1.2, 0.2, 1.2);
        const color = heatmapColor(val);
        const mat = new THREE.MeshPhongMaterial({
          color: color,
          emissive: color,
          emissiveIntensity: 0.15,
        });
        const mesh = new THREE.Mesh(geo, mat);
        const x = startX + c * spacing;
        const z = startZ + r * spacing;
        mesh.position.set(x, -3, z);
        group.add(mesh);

        tiles.push({
          mesh: mesh,
          currentVal: val,
          targetVal: Math.random(),
          speed: 0.3 + Math.random() * 0.5,
          time: Math.random() * 100,
        });
      }
    }

    sceneData.heatTiles = tiles;
  }

  function heatmapColor(val) {
    if (val < 0.25) return 0x1e3a8a;
    if (val < 0.5) return 0x2563eb;
    if (val < 0.75) return 0x06b6d4;
    return 0xf0abfc;
  }

  /* ── Scene 5: Distribution Curve 3D ── */
  function buildDistributionCurve(group, time) {
    const curves = [
      { mean: -3, std: 1.2, color: 0x3b82f6, emissive: 0x2563eb, label: 'Normal' },
      { mean: 0, std: 1.5, color: 0x06b6d4, emissive: 0x0891b2, label: 'Standard' },
      { mean: 3, std: 1.0, color: 0x8b5cf6, emissive: 0x7c3aed, label: 'Skewed' },
    ];

    const pointsPerCurve = 80;
    const curveData = [];
    const allPositions = [];
    const allColors = [];

    curves.forEach(function (curve, ci) {
      const pts = [];
      const step = 10 / pointsPerCurve;
      for (let i = 0; i <= pointsPerCurve; i++) {
        const x = -5 + i * step;
        const dx = (x - curve.mean) / curve.std;
        const y = (1 / (curve.std * Math.sqrt(2 * Math.PI))) * Math.exp(-0.5 * dx * dx);
        pts.push({ x: x, y: y * 6 });
      }

      /* Line strip */
      const linePts = pts.map(function (p) {
        return new THREE.Vector3(p.x, p.y - 2, (ci - 1) * 3.5);
      });
      const lineGeo = new THREE.BufferGeometry().setFromPoints(linePts);
      const lineMat = new THREE.LineBasicMaterial({
        color: curve.color,
        transparent: true,
        opacity: 0.9,
      });
      const line = new THREE.Line(lineGeo, lineMat);
      group.add(line);

      /* Fill area under curve */
      const fillPositions = [];
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i];
        const p1 = pts[i + 1];
        const yBase = -2;
        const z = (ci - 1) * 3.5;
        fillPositions.push(
          p0.x, yBase, z,
          p1.x, yBase, z,
          p0.x, p0.y - 2, z,
          p1.x, yBase, z,
          p1.x, p1.y - 2, z,
          p0.x, p0.y - 2, z
        );
      }
      const fillGeo = new THREE.BufferGeometry();
      fillGeo.setAttribute('position', new THREE.Float32BufferAttribute(fillPositions, 3));
      fillGeo.computeVertexNormals();
      const fillMat = new THREE.MeshBasicMaterial({
        color: curve.color,
        transparent: true,
        opacity: 0.12,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const fillMesh = new THREE.Mesh(fillGeo, fillMat);
      group.add(fillMesh);

      /* Scatter particles along curve */
      const scatterCount = 300;
      const sPositions = [];
      const sColors = [];
      const col = new THREE.Color(curve.color);
      for (let i = 0; i < scatterCount; i++) {
        const t = Math.random();
        const idx = Math.floor(t * (pts.length - 1));
        const frac = t * (pts.length - 1) - idx;
        const p0 = pts[Math.min(idx, pts.length - 1)];
        const p1 = pts[Math.min(idx + 1, pts.length - 1)];
        const sx = p0.x + (p1.x - p0.x) * frac;
        const sy = (p0.y + (p1.y - p0.y) * frac - 2) * (0.3 + Math.random() * 0.7);
        const sz = (ci - 1) * 3.5 + (Math.random() - 0.5) * 2.5;
        sPositions.push(sx, sy, sz);
        sColors.push(col.r * 0.8, col.g * 0.8, col.b * 0.8);
      }
      const sGeo = new THREE.BufferGeometry();
      sGeo.setAttribute('position', new THREE.Float32BufferAttribute(sPositions, 3));
      sGeo.setAttribute('color', new THREE.Float32BufferAttribute(sColors, 3));
      const sMat = new THREE.PointsMaterial({
        size: 0.08,
        sizeAttenuation: true,
        vertexColors: true,
        transparent: true,
        opacity: 0.6,
        blending: THREE.AdditiveBlending,
      });
      const scatter = new THREE.Points(sGeo, sMat);
      group.add(scatter);

      /* Floating data labels (sprites) */
      const labelCanvas = document.createElement('canvas');
      labelCanvas.width = 256;
      labelCanvas.height = 64;
      const ctx = labelCanvas.getContext('2d');
      ctx.fillStyle = 'rgba(0,0,0,0)';
      ctx.fillRect(0, 0, 256, 64);
      ctx.font = 'bold 28px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = '#' + new THREE.Color(curve.color).getHexString();
      ctx.fillText(curve.label, 128, 32);

      const texture = new THREE.CanvasTexture(labelCanvas);
      const spriteMat = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        opacity: 0.7,
      });
      const sprite = new THREE.Sprite(spriteMat);
      const labelIdx = Math.floor(pts.length / 2);
      sprite.position.set(
        pts[labelIdx].x,
        pts[labelIdx].y - 2 + 1.8,
        (ci - 1) * 3.5
      );
      sprite.scale.set(3, 0.75, 1);
      group.add(sprite);

      curveData.push({
        line: line,
        fill: fillMesh,
        scatter: scatter,
        sprite: sprite,
        pts: pts,
        zBase: (ci - 1) * 3.5,
        color: curve.color,
        pulseOffset: ci * 1.2,
      });
    });

    /* Floating data value particles */
    const floatCount = 50;
    const fPositions = [];
    const fSizes = [];
    for (let i = 0; i < floatCount; i++) {
      fPositions.push(
        (Math.random() - 0.5) * 14,
        (Math.random() - 0.5) * 10,
        (Math.random() - 0.5) * 12 - 1
      );
      fSizes.push(0.03 + Math.random() * 0.06);
    }
    const fGeo = new THREE.BufferGeometry();
    fGeo.setAttribute('position', new THREE.Float32BufferAttribute(fPositions, 3));
    fGeo.setAttribute('size', new THREE.Float32BufferAttribute(fSizes, 1));
    const fMat = new THREE.PointsMaterial({
      color: 0x88bbff,
      size: 0.04,
      transparent: true,
      opacity: 0.25,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });
    const floatParticles = new THREE.Points(fGeo, fMat);
    group.add(floatParticles);

    sceneData.distCurves = curveData;
    sceneData.distFloats = { mesh: floatParticles, positions: fPositions };

    /* Lights */
    const ambLight = new THREE.AmbientLight(0x1a3a7a, 0.4);
    group.add(ambLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.6);
    dirLight.position.set(2, 8, 5);
    group.add(dirLight);
  }

  /* ── Scene Update Functions ── */

  function updateBarChart(time) {
    const bars = sceneData.bars;
    if (!bars) return;
    for (let i = 0; i < bars.length; i++) {
      const b = bars[i];
      const wave = Math.sin(time * b.speed + b.offset) * 0.5 + 0.5;
      const h = b.baseHeight * (0.4 + wave * 0.6);
      b.mesh.scale.y = h / b.baseHeight;
      b.mesh.position.y = h * 0.5 - 3;
      b.line.scale.y = h / b.baseHeight;
      b.line.position.y = h * 0.5 - 3;
    }
  }

  function updateScatterPlot(time) {
    const pts = sceneData.scatterPoints;
    if (!pts) return;
    const pos = pts.geometry.attributes.position.array;
    const base = sceneData.scatterBasePos;
    if (!base) return;

    for (let i = 0; i < pos.length; i += 3) {
      const idx = i / 3;
      const noise = Math.sin(time * 0.5 + idx * 0.1) * 0.08;
      pos[i] = base[i] + noise;
      pos[i + 1] = base[i + 1] + Math.sin(time * 0.7 + idx * 0.15) * 0.08;
      pos[i + 2] = base[i + 2] + Math.cos(time * 0.6 + idx * 0.12) * 0.08;
    }
    pts.geometry.attributes.position.needsUpdate = true;

    /* Rotate group */
    pts.rotation.x = Math.sin(time * 0.08) * 0.1;
    pts.rotation.y = time * 0.05;
  }

  function updateWaveChart(time) {
    const pos = sceneData.wavePositions;
    const geo = sceneData.waveGeo;
    if (!pos || !geo) return;

    for (let i = 0; i < pos.length; i += 3) {
      const x = pos[i];
      const y = pos[i + 2];
      const z = Math.sin(x * 0.5 + time * 1.2) * Math.cos(y * 0.5 + time * 0.8) * 2.5;
      pos[i + 1] = z;
    }
    geo.attributes.position.needsUpdate = true;
    geo.computeVertexNormals();

    const sweep = sceneData.sweepGroup;
    if (sweep) {
      const children = sweep.children;
      for (let i = 0; i < children.length; i++) {
        const line = children[i];
        const linePos = line.geometry.attributes.position.array;
        for (let j = 0; j < linePos.length; j += 3) {
          const x = linePos[j];
          const z = Math.sin(x * 0.5 + time * 1.2) * Math.cos(line.position.z * 0.5 + time * 0.8) * 2.5;
          linePos[j + 1] = z;
        }
        line.geometry.attributes.position.needsUpdate = true;
      }
      sweep.position.z = Math.sin(time * 0.15) * 2;
    }
  }

  function updateHeatmap(time) {
    const tiles = sceneData.heatTiles;
    if (!tiles) return;

    for (let i = 0; i < tiles.length; i++) {
      const t = tiles[i];
      t.time += 0.016;

      if (t.time > 1.5) {
        t.targetVal = Math.random();
        t.time = 0;
      }

      t.currentVal += (t.targetVal - t.currentVal) * 0.03;
      const val = t.currentVal;
      const color = new THREE.Color(heatmapColor(val));
      t.mesh.material.color.copy(color);
      t.mesh.material.emissive.copy(color);

      const scaleY = 0.2 + val * 0.6;
      t.mesh.scale.y = scaleY;
      t.mesh.position.y = -3 + scaleY * 0.1;
    }
  }

  function updateDistributionCurve(time) {
    const curves = sceneData.distCurves;
    if (!curves) return;

    /* Gentle pulse on the curves */
    curves.forEach(function (curve, ci) {
      const pulse = 1 + Math.sin(time * 0.6 + curve.pulseOffset) * 0.02;
      curve.line.scale.y = pulse;
      if (curve.fill) curve.fill.scale.y = pulse;
      if (curve.scatter) {
        curve.scatter.rotation.y = Math.sin(time * 0.15 + ci) * 0.04;
        curve.scatter.material.opacity = 0.5 + Math.sin(time * 0.4 + ci) * 0.1;
      }
      if (curve.sprite) {
        curve.sprite.material.opacity = 0.6 + Math.sin(time * 0.5 + ci) * 0.15;
      }
    });

    /* Floating particles drift */
    const floats = sceneData.distFloats;
    if (floats) {
      const pos = floats.mesh.geometry.attributes.position.array;
      for (let i = 0; i < pos.length; i += 3) {
        pos[i] += Math.sin(time * 0.2 + i) * 0.002;
        pos[i + 1] += Math.cos(time * 0.15 + i * 0.5) * 0.002;
        pos[i + 2] += Math.sin(time * 0.1 + i * 0.3) * 0.002;
        if (pos[i] > 8) pos[i] = -8;
        if (pos[i] < -8) pos[i] = 8;
        if (pos[i + 1] > 6) pos[i + 1] = -6;
        if (pos[i + 1] < -6) pos[i + 1] = 6;
      }
      floats.mesh.geometry.attributes.position.needsUpdate = true;
    }
  }

  /* ── Animation Loop ── */

  function animateScene() {
    const delta = sceneClock.getDelta();
    sceneTime += delta;
    sceneTimer += delta * 1000;

    /* Update current scene */
    switch (currentSceneIndex) {
      case 0: updateBarChart(sceneTime); break;
      case 1: updateScatterPlot(sceneTime); break;
      case 2: updateWaveChart(sceneTime); break;
      case 3: updateHeatmap(sceneTime); break;
      case 4: updateDistributionCurve(sceneTime); break;
    }

    /* Update permanent particles */
    updateParticles(delta);

    /* Update robots */
    if (robots.length > 0) updateRobots(sceneTime, delta);

    /* Camera lerp */
    cameraCurrent.lerp(cameraTarget, 0.02);
    camera.position.copy(cameraCurrent);

    /* Handle transitions with easing */
    if (transitionPhase === 'fadeOut') {
      transitionProgress += delta * (1000 / FADE_DURATION);
      var p = Math.min(transitionProgress, 1);
      sceneOpacity = 1 - p * p * (3 - 2 * p);
      if (p >= 1) {
        sceneOpacity = 0;
        doSceneSwap((currentSceneIndex + 1) % 5);
        transitionPhase = 'fadeIn';
        transitionProgress = 0;
      }
    } else if (transitionPhase === 'fadeIn') {
      transitionProgress += delta * (1000 / FADE_DURATION);
      var p = Math.min(transitionProgress, 1);
      sceneOpacity = p * p * (3 - 2 * p);
      if (p >= 1) {
        sceneOpacity = 1;
        transitionPhase = 'none';
        transitionProgress = 0;
      }
    } else {
      if (sceneTimer >= SCENE_DURATION) {
        transitionPhase = 'fadeOut';
        sceneTimer = 0;
      }
    }

    sceneGroup.traverse(function (child) {
      if (child.isMesh || child.isPoints || child.isLine || child.isLineSegments) {
        child.material.transparent = true;
        child.material.opacity = sceneOpacity * (child.userData.baseOpacity || 1);
        child.material.needsUpdate = true;
      }
    });

    camera.lookAt(0, 0, 0);
    renderer.render(mainScene, camera);
    animFrameId = requestAnimationFrame(animateScene);
  }

  function doSceneSwap(newIndex) {
    disposeObject(sceneGroup);
    mainScene.remove(sceneGroup);

    sceneTimer = 0;
    currentSceneIndex = newIndex;
    sceneGroup = buildScene(currentSceneIndex, sceneTime);
    mainScene.add(sceneGroup);

    cameraTarget.set(
      CAMERA_POSITIONS[currentSceneIndex].x,
      CAMERA_POSITIONS[currentSceneIndex].y,
      CAMERA_POSITIONS[currentSceneIndex].z
    );

    updateSceneIndicator();
  }

  function jumpToScene(index) {
    if (index === currentSceneIndex && transitionPhase === 'none') return;
    if (index < 0 || index > 4) return;

    doSceneSwap(index);
    sceneOpacity = 0;
    transitionPhase = 'fadeIn';
  }

  function updateSceneIndicator() {
    document.querySelectorAll('.scene-dot').forEach(function (dot, i) {
      dot.classList.toggle('active', i === currentSceneIndex);
    });
    var nameEl = document.getElementById('scene-name');
    if (nameEl) nameEl.textContent = SCENE_NAMES[currentSceneIndex];
  }

  /* ── Permanent Objects ── */

  let particleSystem;
  let particleSpeeds = [];


  function buildPermanentObjects(scene) {
    /* Particles */
    const count = particleCount;
    const positions = new Float32Array(count * 3);
    particleSpeeds = [];

    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 50;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 25;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 30 - 5;
      particleSpeeds.push({
        x: (Math.random() - 0.5) * 0.005,
        y: 0.003 + Math.random() * 0.008,
        z: (Math.random() - 0.5) * 0.005,
      });
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const mat = new THREE.PointsMaterial({
      color: 0x88bbff,
      size: isMobile ? 0.04 : 0.05,
      transparent: true,
      opacity: 0.4,
      blending: THREE.AdditiveBlending,
      sizeAttenuation: true,
    });

    particleSystem = new THREE.Points(geo, mat);
    scene.add(particleSystem);

    /* Grid floor */
    const gridHelper = new THREE.GridHelper(40, 40, 0x2563eb, 0x1a3a6a);
    gridHelper.position.y = -3.2;
    gridHelper.material.opacity = 0.12;
    gridHelper.material.transparent = true;
    scene.add(gridHelper);

    const gridHelper2 = new THREE.GridHelper(40, 10, 0x3b82f6, 0x2563eb);
    gridHelper2.position.y = -3.15;
    gridHelper2.material.opacity = 0.06;
    gridHelper2.material.transparent = true;
    scene.add(gridHelper2);

  }

  function updateParticles(delta) {
    if (!particleSystem) return;
    const pos = particleSystem.geometry.attributes.position.array;
    const count = particleCount;

    for (let i = 0; i < count; i++) {
      pos[i * 3] += particleSpeeds[i].x;
      pos[i * 3 + 1] += particleSpeeds[i].y;
      pos[i * 3 + 2] += particleSpeeds[i].z;

      if (pos[i * 3 + 1] > 14) {
        pos[i * 3] = (Math.random() - 0.5) * 50;
        pos[i * 3 + 1] = -10;
        pos[i * 3 + 2] = (Math.random() - 0.5) * 30 - 5;
      }
    }
    particleSystem.geometry.attributes.position.needsUpdate = true;
  }

  /* ── Init Three.js ── */

  function initThreeScene() {
    const canvas = document.getElementById('three-canvas');
    if (!canvas) return;

    mainScene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 100);

    renderer = new THREE.WebGLRenderer({
      canvas: canvas,
      antialias: true,
      alpha: true,
    });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    /* Ambient light for all scenes */
    const ambient = new THREE.AmbientLight(0x1a2a4a, 0.6);
    mainScene.add(ambient);

    /* Build permanent objects */
    buildPermanentObjects(mainScene);

    /* Build initial scene */
    sceneGroup = buildScene(0, 0);
    mainScene.add(sceneGroup);
    sceneOpacity = 1;

    /* Set camera position based on initial scene */
    camera.position.set(0, 8, 20);
    cameraTarget.set(0, 8, 20);
    cameraCurrent.set(0, 8, 20);

    /* Start animation loop */
    sceneClock = new THREE.Clock();
    animateScene();

    /* ── Resize ── */
    window.addEventListener('resize', function () {
      const w = window.innerWidth;
      const h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });

    /* ── Visibility ── */
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) {
        sceneClock.stop();
      } else {
        sceneClock = new THREE.Clock();
      }
    });
  }

  /* ═══════════════════════════════════════════════════════
     SCENE INDICATOR — UI
     ═══════════════════════════════════════════════════════ */

  function initSceneIndicator() {
    document.querySelectorAll('.scene-dot').forEach(function (dot) {
      dot.addEventListener('click', function () {
        const index = parseInt(this.getAttribute('data-index'), 10);
        jumpToScene(index);
      });
    });
  }

  /* ═══════════════════════════════════════════════════════
     NAVBAR — SCROLL EFFECT
     ═══════════════════════════════════════════════════════ */

  function initNavbar() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;

    let ticking = false;
    window.addEventListener('scroll', function () {
      if (!ticking) {
        window.requestAnimationFrame(function () {
          if (window.scrollY > 40) {
            navbar.classList.add('scrolled');
          } else {
            navbar.classList.remove('scrolled');
          }
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  /* ═══════════════════════════════════════════════════════
     MOBILE HAMBURGER MENU
     ═══════════════════════════════════════════════════════ */

  function initMobileMenu() {
    const hamburger = document.getElementById('nav-hamburger');
    const navLinks = document.getElementById('nav-links');
    if (!hamburger || !navLinks) return;

    hamburger.addEventListener('click', function () {
      const isOpen = navLinks.classList.toggle('open');
      hamburger.classList.toggle('active', isOpen);
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    navLinks.querySelectorAll('.nav-link').forEach(function (link) {
      link.addEventListener('click', function () {
        navLinks.classList.remove('open');
        hamburger.classList.remove('active');
        document.body.style.overflow = '';
      });
    });
  }

  /* ═══════════════════════════════════════════════════════
     INTERSECTION OBSERVER — REVEAL ANIMATIONS
     ═══════════════════════════════════════════════════════ */

  function initRevealAnimations() {
    const revealEls = document.querySelectorAll('.reveal');
    if (!revealEls.length) return;

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (entry) {
            if (entry.isIntersecting) {
              entry.target.classList.add('visible');
              observer.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
      );

      revealEls.forEach(function (el) {
        observer.observe(el);
      });
    } else {
      revealEls.forEach(function (el) {
        el.classList.add('visible');
      });
    }
  }

  /* ═══════════════════════════════════════════════════════
     SMOOTH SCROLL FOR ANCHOR LINKS
     ═══════════════════════════════════════════════════════ */

  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        const targetId = this.getAttribute('href');
        if (!targetId || targetId === '#') return;

        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          const navH = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-h'), 10) || 72;
          const top = target.getBoundingClientRect().top + window.pageYOffset - navH - 16;
          window.scrollTo({ top: top, behavior: 'smooth' });
        }
      });
    });
  }

  /* ═══════════════════════════════════════════════════════
     ROBOT 3D CHARACTERS — merger dengan scene yang sama
     ═══════════════════════════════════════════════════════ */

  function initRobots() {
    const loader = new THREE.GLTFLoader();
    const path = '/static/assets/robot.glb';

    loader.load(
      path,

      function (gltf) {
        const configs = [
          { x: 4.5, y: -0.5, z: 0, s: 6.0, rotY: -0.3, spd: 1.2, rX: 14, rY: 4, rZ: 8 },
          { x: -3, y: 0.8, z: 2, s: 6.0, rotY: 0.2, spd: 1.2, rX: 14, rY: 4, rZ: 8 },
          { x: -7, y: -1.2, z: -2, s: 6.0, rotY: 0.4, spd: 1.2, rX: 14, rY: 4, rZ: 8 },
        ];

        configs.forEach(function (cfg) {
          var r = createRobot(gltf, cfg);
          robots.push(r);
          robotMixers.push(r.mixer);
        });

        setTimeout(function () {
          robots.forEach(function (r) { triggerWave(r); });
        }, 1400);

        initRobotParticles();

        robotAccentLight = new THREE.PointLight(0x2563eb, 1.5, 15);
        mainScene.add(robotAccentLight);

        setupRobotClick();
      },

      function (xhr) {
        if (xhr.total > 0)
          console.log('[robot]', (xhr.loaded / xhr.total * 100).toFixed(0) + '%');
      },

      function (err) { console.error('[robot] Load error:', err); }
    );
  }

  function createRobot(gltf, cfg) {
    var mesh = gltf.scene.clone();
    mesh.scale.set(cfg.s, cfg.s, cfg.s);
    mesh.position.set(cfg.x, cfg.y, cfg.z || 0);
    mesh.rotation.y = cfg.rotY;

    mesh.traverse(function (c) {
      if (c.isMesh) {
        c.castShadow = c.receiveShadow = true;
        if (c.material) { c.material.envMapIntensity = 1.2; c.material.needsUpdate = true; }
      }
    });
    mainScene.add(mesh);

    var mixer = new THREE.AnimationMixer(mesh);
    gltf.animations.forEach(function (clip) {
      var a = mixer.clipAction(clip);
      a.reset(); a.setLoop(THREE.LoopRepeat, Infinity); a.play();
    });

    // Cari bone tangan — pilih paling dalam
    var allArms = [];
    mesh.traverse(function (c) {
      if (!c.isBone) return;
      var n = (c.name || '').toLowerCase();
      if (/arm|hand|lengan|tangan|shoulder|radius|humerus|wrist|forearm|elbow|jari/.test(n)) allArms.push(c);
    });
    function depthOf(b) { var d = 0, p = b; while (p.parent) { d++; p = p.parent; } return d; }
    allArms.sort(function (a, b) { return depthOf(b) - depthOf(a); });
    var right = allArms.filter(function (a) { return /right|kanan/.test(a.name || ''); });
    var armBone = right.length > 0 ? right[0] : (allArms[0] || null);

    return {
      mesh: mesh, mixer: mixer, armBone: armBone, origScale: cfg.s,
      spd: cfg.spd, rX: cfg.rX, rY: cfg.rY, rZ: cfg.rZ || 4,
      isBusy: false, isWaving: false, wavePhase: 0, waveEndT: 0,
      driftVX: 0, driftVY: 0, driftVZ: 0,
      driftTargetX: 0, driftTargetY: 0, driftTargetZ: 0,
      timeOutside: 0, angryUntil: 0,
    };
  }

  function triggerWave(r) {
    r.isWaving = true;
    r.wavePhase = 0;
    r.waveEndT = sceneTime + 2.0;
  }

  function triggerDrift(r, cb) {
    var steps = 5 + Math.floor(Math.random() * 4);
    var tl = gsap.timeline({ onComplete: function () { if (cb) cb(); } });
    for (var i = 0; i < steps; i++) {
      var dx = (Math.random() - 0.5) * 3;
      var dy = (Math.random() - 0.5) * 1.5;
      var lookY = -0.3 + (dx > 0 ? 0.25 : -0.25);
      var dur = 0.2 + Math.random() * 0.3;
      tl.to(r.mesh.rotation, { y: lookY, z: dx * 0.04, duration: dur * 0.4, ease: 'power1.out' });
      tl.to(r.mesh.position, { x: '+=' + dx, y: '+=' + dy, duration: dur, ease: 'power2.inOut' }, '+=0.03');
    }
  }

  function initRobotParticles() {
    var count = 800;
    var pGeo = new THREE.BufferGeometry();
    var pPos = new Float32Array(count * 3);
    var pCol = new Float32Array(count * 3);
    var palette = [
      [0.02, 0.71, 0.83], [0.29, 0.24, 0.93],
      [0.49, 0.18, 0.93], [0.96, 0.42, 0.71],
    ];
    for (var i = 0; i < count; i++) {
      pPos[i*3]   = (Math.random() - 0.5) * 26;
      pPos[i*3+1] = (Math.random() - 0.5) * 14;
      pPos[i*3+2] = -2 - Math.random() * 8;
      var c = palette[Math.floor(Math.random() * palette.length)];
      pCol[i*3] = c[0]; pCol[i*3+1] = c[1]; pCol[i*3+2] = c[2];
      robotParticleVel.push({
        x: (Math.random() - 0.5) * 0.008,
        y: (Math.random() - 0.5) * 0.008,
        phase: Math.random() * Math.PI * 2,
      });
    }
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
    pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 3));
    var pMat = new THREE.PointsMaterial({
      size: 0.12, transparent: true, opacity: 0.7,
      blending: THREE.AdditiveBlending, vertexColors: true, depthWrite: false,
    });
    robotParticles = new THREE.Points(pGeo, pMat);
    mainScene.add(robotParticles);
    robotParticleGeo = pGeo;
  }

  function updateRobots(time, delta) {
    if (robots.length === 0) return;

    robots.forEach(function (r, idx) {
      if (r.mixer) r.mixer.update(delta);

      if (!r.isBusy) {
        var changeRate = 0.02;
        if (Math.random() < changeRate) r.driftTargetX = (Math.random() - 0.5) * r.rX;
        if (Math.random() < changeRate) r.driftTargetY = (Math.random() - 0.5) * r.rY * 0.5;
        if (Math.random() < changeRate) r.driftTargetZ = (Math.random() - 0.5) * r.rZ;
        r.driftVX += (r.driftTargetX - r.driftVX) * 0.03;
        r.driftVY += (r.driftTargetY - r.driftVY) * 0.03;
        r.driftVZ += (r.driftTargetZ - r.driftVZ) * 0.03;
        r.mesh.position.x += r.driftVX * delta * r.spd;
        r.mesh.position.y += r.driftVY * delta * r.spd;
        r.mesh.position.z += r.driftVZ * delta * r.spd;

        var inView = r.mesh.position.x > -15 && r.mesh.position.x < 15
                  && r.mesh.position.y > -8 && r.mesh.position.y < 8
                  && r.mesh.position.z > -12 && r.mesh.position.z < 12;
        if (inView) r.timeOutside = 0;
        else {
          r.timeOutside += delta;
          if (r.timeOutside > 4) {
            r.driftTargetX = -r.mesh.position.x * 0.1;
            r.driftTargetY = -r.mesh.position.y * 0.1;
            r.driftTargetZ = -r.mesh.position.z * 0.1;
          }
        }

        var lookY = -0.3 + r.driftVX * 0.25;
        r.mesh.rotation.y += (lookY - r.mesh.rotation.y) * 0.03;
        r.mesh.position.y += Math.sin(time * 1.5 + idx * 2.1) * 0.004;
      }

      /* Speech bubble follows robot */
      if (r.speechBubble && r.speechBubble.parent) {
        r.speechBubble.position.x = r.mesh.position.x;
        r.speechBubble.position.z = r.mesh.position.z;
      }

      // ── Collision repulsion ──
      for (var j = 0; j < robots.length; j++) {
        if (j === idx) continue;
        var other = robots[j];
        var dx = r.mesh.position.x - other.mesh.position.x;
        var dy = r.mesh.position.y - other.mesh.position.y;
        var dz = r.mesh.position.z - other.mesh.position.z;
        var dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
        var minDist = 4.0;
        if (dist < minDist && dist > 0.01) {
          var force = (minDist - dist) / minDist * 0.5;
          var nx = dx / dist, ny = dy / dist, nz = dz / dist;
          r.mesh.position.x += nx * force * delta * 2;
          r.mesh.position.y += ny * force * delta * 2;
          r.mesh.position.z += nz * force * delta * 2;
        }
      }

      // Wave via quaternion
      if (r.isWaving && r.armBone) {
        if (time < r.waveEndT) {
          r.wavePhase += delta * 6;
          var amp = Math.min((time - (r.waveEndT - 2.0)) / 0.3, 1);
          var fadeOut = Math.max((r.waveEndT - time) / 0.3, 0);
          var e = amp * fadeOut;
          var sin = Math.sin(r.wavePhase);
          var q = new THREE.Quaternion()
            .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), sin * 0.8 * e))
            .multiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1, 0, 0), -0.25 * e));
          r.armBone.quaternion.premultiply(q);
        } else {
          r.isWaving = false;
        }
      }
    });

    // Robot particles
    if (robotParticles && robotParticleGeo) {
      var pos = robotParticleGeo.attributes.position.array;
      for (var i = 0; i < 800; i++) {
        pos[i*3]   += robotParticleVel[i].x + Math.sin(time * 0.3 + robotParticleVel[i].phase) * 0.001;
        pos[i*3+1] += robotParticleVel[i].y + Math.cos(time * 0.2 + robotParticleVel[i].phase) * 0.001;
        if (pos[i*3] > 15) pos[i*3] = -15;
        if (pos[i*3] < -15) pos[i*3] = 15;
        if (pos[i*3+1] > 8) pos[i*3+1] = -8;
        if (pos[i*3+1] < -8) pos[i*3+1] = 8;
      }
      robotParticleGeo.attributes.position.needsUpdate = true;
    }

    // Accent light orbit
    if (robotAccentLight) {
      robotAccentLight.position.x = Math.sin(time * 0.6) * 6;
      robotAccentLight.position.z = Math.cos(time * 0.6) * 6;
      robotAccentLight.position.y = 3;
      var cols = [0x2563eb, 0x06b6d4, 0x7c3aed, 0xf472b6];
      robotAccentLight.color.setHex(cols[Math.floor(time * 0.4) % cols.length]);
    }
  }

  function setupRobotClick() {
    var canvas = document.getElementById('three-canvas');
    if (!canvas) return;
    var raycaster = new THREE.Raycaster();
    var mouse = new THREE.Vector2();
    canvas.addEventListener('click', function (e) {
      var rect = canvas.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      for (var i = robots.length - 1; i >= 0; i--) {
        var r = robots[i];
        var hits = raycaster.intersectObject(r.mesh, true);
        if (hits.length > 0 && !r.isBusy) {
          r.isBusy = true;
          triggerWave(r);
          triggerDrift(r, function () { r.isBusy = false; });
          break;
        }
      }
    });
  }

  /* ═══════════════════════════════════════════════════════
     GREETING — Time-aware + returning visitor
     ═══════════════════════════════════════════════════════ */

  function makeSpeechBubble(text, color) {
    var canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 128;
    var ctx = canvas.getContext('2d');

    /* Bubble background */
    var bx = 20, by = 10, bw = 216, bh = 80;
    ctx.fillStyle = 'rgba(15,23,42,0.85)';
    ctx.beginPath();
    ctx.roundRect(bx, by, bw, bh, 16);
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(bx, by, bw, bh, 16);
    ctx.stroke();

    /* Tail */
    ctx.fillStyle = 'rgba(15,23,42,0.85)';
    ctx.beginPath();
    ctx.moveTo(140, 90);
    ctx.lineTo(160, 118);
    ctx.lineTo(180, 90);
    ctx.closePath();
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(140, 90);
    ctx.lineTo(160, 118);
    ctx.lineTo(180, 90);
    ctx.closePath();
    ctx.stroke();

    /* Text */
    ctx.font = 'bold 28px "JetBrains Mono", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#f1f5f9';
    ctx.fillText(text, 128, 52);

    var texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    var mat = new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0,
      depthTest: false,
    });
    return new THREE.Sprite(mat);
  }

  function triggerRobotGreeting() {
    var greetings = ['Hello!', 'Welcome!', 'Hi there!', 'Hey!'];
    robots.forEach(function (r, i) {
      r.isWaving = true;
      r.wavePhase = 0;
      r.waveEndT = sceneTime + 3.5 + i * 0.3;
      /* Drift toward center briefly */
      r.driftTargetX = -r.mesh.position.x * 0.15;
      r.driftTargetY = -r.mesh.position.y * 0.15;

      /* Speech bubble */
      var colors = ['#06b6d4', '#3b82f6', '#a855f7', '#f472b6'];
      var bubbleText = greetings[i % greetings.length];
      var bubble = makeSpeechBubble(bubbleText, colors[i % colors.length]);
      bubble.position.set(
        r.mesh.position.x,
        r.mesh.position.y + 2.2,
        r.mesh.position.z
      );
      bubble.scale.set(2.2, 1.1, 1);
      mainScene.add(bubble);

      /* Animate in */
      gsap.to(bubble.material, {
        opacity: 1,
        duration: 0.4,
        ease: 'power2.out',
        delay: i * 0.15,
      });
      /* Float up slightly */
      gsap.to(bubble.position, {
        y: r.mesh.position.y + 2.8,
        duration: 1.2,
        ease: 'sine.inOut',
        yoyo: true,
        repeat: 1,
        delay: i * 0.15,
      });
      /* Fade out and remove */
      gsap.to(bubble.material, {
        opacity: 0,
        duration: 0.5,
        ease: 'power2.in',
        delay: 2.5 + i * 0.15,
        onComplete: function () {
          mainScene.remove(bubble);
          bubble.material.map.dispose();
          bubble.material.dispose();
        },
      });

      r.speechBubble = bubble;
    });
  }

  function initGreeting() {
    var toast = document.getElementById('greeting-toast');
    var icon = document.getElementById('greeting-icon');
    var text = document.getElementById('greeting-text');
    var sub = document.getElementById('greeting-sub');
    var closeBtn = document.getElementById('greeting-close');
    if (!toast || !text) return;

    /* Time-based greeting */
    var hour = new Date().getHours();
    var greeting, faIcon;
    if (hour < 12) {
      greeting = 'Good Morning!';
      faIcon = 'fa-sun';
    } else if (hour < 17) {
      greeting = 'Good Afternoon!';
      faIcon = 'fa-cloud-sun';
    } else if (hour < 21) {
      greeting = 'Good Evening!';
      faIcon = 'fa-moon';
    } else {
      greeting = 'Good Night!';
      faIcon = 'fa-star';
    }

    /* First visit vs returning visitor */
    var visited = localStorage.getItem('dsg_visited');
    var name = localStorage.getItem('dsg_name');
    var subMsg;
    if (!visited) {
      subMsg = 'Welcome to DS Generator — your Auto-EDA dashboard';
      localStorage.setItem('dsg_visited', 'true');
      localStorage.setItem('dsg_visit_count', '1');
    } else {
      var count = parseInt(localStorage.getItem('dsg_visit_count') || '1', 10) + 1;
      localStorage.setItem('dsg_visit_count', count.toString());
      if (count < 5) {
        subMsg = 'Welcome back! Ready to analyze your data?';
      } else {
        var messages = [
          'Great to see you again! Your data is waiting.',
          'Back for more insights? Let\'s dive in!',
          'Welcome back! New discoveries await.',
        ];
        subMsg = messages[Math.floor(Math.random() * messages.length)];
      }
    }

    if (icon) icon.innerHTML = '<i class="fas ' + faIcon + '"></i>';
    text.textContent = greeting;
    sub.textContent = subMsg;

    /* Show with delay + robot greeting */
    setTimeout(function () {
      toast.classList.add('show');
      if (robots.length > 0) triggerRobotGreeting();
    }, 1200);

    /* Auto-hide after 5s */
    var autoHide = setTimeout(function () {
      toast.classList.remove('show');
    }, 6000);

    /* Manual close */
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        toast.classList.remove('show');
        clearTimeout(autoHide);
      });
    }
  }

  /* ═══════════════════════════════════════════════════════
     INIT
     ═══════════════════════════════════════════════════════ */

  function init() {
    initThreeScene();
    initRobots();
    initSceneIndicator();
    initGreeting();
    initNavbar();
    initMobileMenu();
    initRevealAnimations();
    initSmoothScroll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
