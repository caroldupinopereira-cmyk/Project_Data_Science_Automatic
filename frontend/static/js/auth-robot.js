(function () {
    'use strict';

    var canvas = document.getElementById('robotCanvas');
    if (!canvas || typeof THREE === 'undefined' || typeof THREE.GLTFLoader === 'undefined') return;

    var scene, camera, renderer, clock, composer;
    var robot = null;
    var eyes = [];
    var hands = [];
    var handOrigins = [];
    var particles = null;
    var glowLight = null;
    var glowRing = null;

    var nextBlink = 3;
    var blinkPhase = 0;
    var blinking = false;
    var nextWave = 4;
    var wavePhase = 0;
    var waving = false;

    function init() {
        clock = new THREE.Clock();
        scene = new THREE.Scene();
        camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
        camera.position.set(0, 0.2, 6);
        camera.lookAt(0, -0.2, 0);

        renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        renderer.setClearColor(0x000000, 0);
        renderer.toneMapping = THREE.ReinhardToneMapping;
        renderer.toneMappingExposure = 1.1;

        resize();
        window.addEventListener('resize', resize);

        if (typeof THREE.EffectComposer !== 'undefined' && typeof THREE.UnrealBloomPass !== 'undefined') {
            composer = new THREE.EffectComposer(renderer);
            composer.addPass(new THREE.RenderPass(scene, camera));
            composer.addPass(new THREE.UnrealBloomPass(
                new THREE.Vector2(window.innerWidth, window.innerHeight), 0.6, 0.3, 0.2
            ));
        }

        scene.add(new THREE.AmbientLight(0x9999cc, 0.35));

        var key = new THREE.DirectionalLight(0xffffff, 0.9);
        key.position.set(4, 5, 5);
        scene.add(key);

        var rim = new THREE.DirectionalLight(0x38bdf8, 2.0);
        rim.position.set(-4, 2, -5);
        scene.add(rim);

        var fill = new THREE.PointLight(0x7c3aed, 1.5, 14);
        fill.position.set(-2, -1, 3);
        scene.add(fill);

        var accent = new THREE.PointLight(0x2563eb, 1.8, 12);
        accent.position.set(2, 3, 2);
        scene.add(accent);

        var underLight = new THREE.PointLight(0x38bdf8, 1.0, 8);
        underLight.position.set(0, -2, 1);
        scene.add(underLight);

        loadRobot();
        initParticles();
        initGlow();
        animate();
    }

    function resize() {
        var parent = canvas.parentElement;
        var w = parent ? parent.clientWidth : window.innerWidth;
        var h = parent ? parent.clientHeight : Math.floor(window.innerHeight * 0.6);
        if (!w || !h) { w = window.innerWidth; h = Math.floor(window.innerHeight * 0.6); }
        canvas.width = w;
        canvas.height = h;
        canvas.style.cssText = 'width:' + w + 'px;height:' + h + 'px';
        if (camera) { camera.aspect = w / h; camera.updateProjectionMatrix(); }
        if (renderer) renderer.setSize(w, h);
        if (composer) composer.setSize(w, h);
    }

    function loadRobot() {
        var loader = new THREE.GLTFLoader();
        loader.load('/static/assets/robot.glb', function (gltf) {
            robot = gltf.scene.clone();
            robot.scale.set(2.8, 2.8, 2.8);
            robot.position.set(0, -0.6, 0);
            robot.rotation.y = -0.1;

            robot.traverse(function (c) {
                if (!c.isMesh) return;
                c.castShadow = c.receiveShadow = true;
                var n = c.name.toLowerCase();
                if (/eye/.test(n)) { eyes.push(c); }
                if (/hand/.test(n)) {
                    hands.push(c);
                    handOrigins.push({ x: c.position.x, y: c.position.y, z: c.position.z });
                }
            });

            scene.add(robot);
        }, undefined, function (err) { console.warn('[robot] load error:', err); });
    }

    function ease(t) { return -(Math.cos(Math.PI * t) - 1) / 2; }

    function initParticles() {
        var count = 250;
        var geo = new THREE.BufferGeometry();
        var pos = new Float32Array(count * 3);
        var cols = new Float32Array(count * 3);
        var pals = [
            [0.22, 0.74, 0.98],
            [0.49, 0.55, 1.0],
            [0.3, 0.8, 1.0],
            [1.0, 1.0, 1.0],
        ];
        for (var i = 0; i < count; i++) {
            var theta = Math.random() * Math.PI * 2;
            var phi = Math.acos(2 * Math.random() - 1);
            var r = 1.2 + Math.random() * 2.5;
            pos[i * 3]     = Math.sin(phi) * Math.cos(theta) * r;
            pos[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * r;
            pos[i * 3 + 2] = Math.cos(phi) * r - 0.5;
            var c = pals[Math.floor(Math.random() * pals.length)];
            cols[i * 3] = c[0]; cols[i * 3 + 1] = c[1]; cols[i * 3 + 2] = c[2];
        }
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(cols, 3));

        particles = new THREE.Points(geo, new THREE.PointsMaterial({
            size: 0.03,
            transparent: true,
            opacity: 0.5,
            blending: THREE.AdditiveBlending,
            vertexColors: true,
            depthWrite: false,
            sizeAttenuation: true,
        }));
        scene.add(particles);
    }

    function initGlow() {
        glowLight = new THREE.PointLight(0x38bdf8, 1.0, 6);
        glowLight.position.set(0, -1.2, 1);
        scene.add(glowLight);

        var ringGeo = new THREE.RingGeometry(0.8, 1.2, 64);
        var ringMat = new THREE.MeshBasicMaterial({
            color: 0x38bdf8,
            transparent: true,
            opacity: 0.06,
            blending: THREE.AdditiveBlending,
            side: THREE.DoubleSide,
            depthWrite: false,
        });
        glowRing = new THREE.Mesh(ringGeo, ringMat);
        glowRing.position.set(0, -1.4, 0.5);
        glowRing.rotation.x = -Math.PI / 2;
        scene.add(glowRing);
    }

    function animate() {
        requestAnimationFrame(animate);
        var dt = clock.getDelta();
        var t = clock.getElapsedTime();

        if (robot) {
            robot.position.x = Math.sin(t * 0.3) * 0.15;
            robot.position.y = -0.6 + Math.sin(t * 0.8) * 0.04;
            robot.rotation.y = -0.1 + Math.sin(t * 0.2) * 0.06;
            robot.rotation.z = Math.sin(t * 0.35) * 0.015;
        }

        if (eyes.length > 0) {
            if (!blinking) {
                nextBlink -= dt;
                if (nextBlink <= 0) { blinking = true; blinkPhase = 0; }
            }
            if (blinking) {
                blinkPhase += dt * 10;
                var s = blinkPhase < 0.5 ? 1 - ease(blinkPhase * 2) : ease((blinkPhase - 0.5) * 2);
                s = Math.max(0.01, s);
                for (var i = 0; i < eyes.length; i++) {
                    eyes[i].scale.y = s;
                    var m = eyes[i].material;
                    if (m) { if (!m.transparent) m.transparent = true; m.opacity = s; m.needsUpdate = true; }
                }
                if (blinkPhase >= 1) {
                    blinking = false;
                    nextBlink = 2.5 + Math.random() * 4;
                    for (var j = 0; j < eyes.length; j++) {
                        eyes[j].scale.y = 1;
                        var m2 = eyes[j].material;
                        if (m2) { m2.opacity = 1; m2.needsUpdate = true; }
                    }
                }
            }
        }

        if (hands.length > 0) {
            if (!waving) {
                nextWave -= dt;
                if (nextWave <= 0) { waving = true; wavePhase = 0; }
            }
            if (waving) {
                wavePhase += dt * 1.4;
                var wp = Math.min(wavePhase, 1);
                var lift = wp < 0.3 ? ease(wp / 0.3) :
                    wp < 0.75 ? 1 + Math.sin(((wp - 0.3) / 0.45) * Math.PI * 3) * 0.35 :
                    ease(1 - (wp - 0.75) / 0.25) * 0.5;
                for (var k = 0; k < hands.length; k++) {
                    hands[k].position.y = handOrigins[k].y + lift * 0.35;
                    hands[k].rotation.z = Math.sin(wp * Math.PI * 3.5) * 0.45 * Math.min(1, lift * 3);
                }
                if (wavePhase >= 1) {
                    waving = false;
                    nextWave = 3.5 + Math.random() * 4;
                    for (var m = 0; m < hands.length; m++) {
                        hands[m].position.y = handOrigins[m].y;
                        hands[m].rotation.z = 0;
                    }
                }
            }
        }

        if (glowLight) {
            glowLight.intensity = 0.8 + Math.sin(t * 0.4) * 0.3;
            glowLight.color.setHSL(0.55 + Math.sin(t * 0.15) * 0.05, 0.7, 0.5);
        }
        if (glowRing) {
            glowRing.scale.setScalar(1 + Math.sin(t * 0.3) * 0.08);
            glowRing.material.opacity = 0.04 + Math.sin(t * 0.4) * 0.02;
        }

        if (particles) {
            var pp = particles.geometry.attributes.position.array;
            for (var p = 0; p < pp.length; p += 3) {
                pp[p]     += Math.sin(t * 0.3 + p * 0.25) * 0.0006;
                pp[p + 1] += Math.cos(t * 0.25 + p * 0.18) * 0.0005;
                pp[p + 2] += Math.sin(t * 0.35 + p * 0.12) * 0.0004;
            }
            particles.geometry.attributes.position.needsUpdate = true;
            particles.rotation.y += 0.0005;
            particles.material.opacity = 0.35 + Math.sin(t * 0.5) * 0.15;
        }

        if (composer) composer.render();
        else renderer.render(scene, camera);
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
