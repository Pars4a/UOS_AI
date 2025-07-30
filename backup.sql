--
-- PostgreSQL database dump
--

-- Dumped from database version 15.13 (Debian 15.13-1.pgdg120+1)
-- Dumped by pg_dump version 15.13 (Debian 15.13-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: info; Type: TABLE; Schema: public; Owner: cloud_man
--

CREATE TABLE public.info (
    id integer NOT NULL,
    category character varying(255),
    key character varying(255),
    value text
);


ALTER TABLE public.info OWNER TO cloud_man;

--
-- Name: info_id_seq; Type: SEQUENCE; Schema: public; Owner: cloud_man
--

CREATE SEQUENCE public.info_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.info_id_seq OWNER TO cloud_man;

--
-- Name: info_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: cloud_man
--

ALTER SEQUENCE public.info_id_seq OWNED BY public.info.id;


--
-- Name: info id; Type: DEFAULT; Schema: public; Owner: cloud_man
--

ALTER TABLE ONLY public.info ALTER COLUMN id SET DEFAULT nextval('public.info_id_seq'::regclass);


--
-- Data for Name: info; Type: TABLE DATA; Schema: public; Owner: cloud_man
--

COPY public.info (id, category, key, value) FROM stdin;
1	staff	head of computer engineering	Dr Shwan Chatto
2	staff	lecturers of computer engineering	Jaza Faiq Gul-Mohammed , Sarwat Ali Ahmed,Twana saeed Ali, Mohammed Abdulla Ali, Alle Abdulrahim Hussein, Taymaa Hussein, Shelan Raheem
4	classes, subjects	classes of computer engineering, first semester	University Work Envicornment, English Language Level 1,2, Kurdology, Calculus1, Electrical Circuits, Compputer Fundamentals, Engineering Drawing
5	classes, subjects	classes of computer engineering	second semester: Logic Design1, Calculus 2, Physical Education, English lang level 3, Physical Electronics, Professional Skills, Programming Concepts and Algorithms(in Java)
6	Parallel Prices	parallel, price, نزخ	architectural engineering: 2,750,000 IQD computer engineering: 2,750,000 IQD civil engineering: 2,250,000 IQD electrical engineering 2,250,000 IQD water resources engineering 2,250,000 IQD
8	staff	computer engineering assistant head, بڕیاردەری بەش	Rizgar Salih, ڕزگار ساڵح
9	Colleges of UOS	colleges	Engineering, Medicine, science, commerce, basic education, Humanities education, College of Administration, Veterinary Medicine
10	president	name	Dr Kosar Mohammed Ali
19	Courses	Electrical Engineering	In the first semester: Electrical Circuit 1, Physical Electronic, Linear Algebra, Information Technology, English Level 2, University Work Environment, Circuit Lab, Electronic Lab, Computer Lab. In the second semester: Electronic Circuit 2, Calculus 1, Kurdology, English Level 3, Physical Education, Professional skills, Workshop Lab, Drawing Lab. In the third semester: Digital Electronics 1, Analogue Electronics 1, DC Machine, Mechanical Engineering, Calculus 2, Computer Programming, Digital Lab, Analogue Lab, DC Machine Lab, Mechanic Lab, C++ Programming Lab. In the fourth semester: Circuit Analysis, Electromagnetic Field, Communication 1, Electrical Measure & Material, Engineering Analysis, Numerical Analysis, Communication Lab, Electrical Measurement Lab, Circuit Network {Ma} Lab, Numerical Analysis Lab. In the fifth semester: Power Engineering 1, Control Engineering 1, Communication 2, Digital Electronics 2, Antenna, Economy, Power Lab, Control Lab, Communication Lab, Digital Lab, Computer Apps {Ma} Lab. In the sixth semester: Power Engineering 2, Control Engineering 2, Digital Communication, Microprocessor & Microcontrol, Analogue Electronics 2, AC Machine, Digital Communication Lab, Microprocessor & Microcontrol Lab, Analogue Lab, AC Machine Lab, Induction Machine Lab, Computer Apps {Au} Lab.
\.


--
-- Name: info_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cloud_man
--

SELECT pg_catalog.setval('public.info_id_seq', 19, true);


--
-- Name: info info_pkey; Type: CONSTRAINT; Schema: public; Owner: cloud_man
--

ALTER TABLE ONLY public.info
    ADD CONSTRAINT info_pkey PRIMARY KEY (id);


--
-- Name: ix_info_category; Type: INDEX; Schema: public; Owner: cloud_man
--

CREATE INDEX ix_info_category ON public.info USING btree (category);


--
-- Name: ix_info_id; Type: INDEX; Schema: public; Owner: cloud_man
--

CREATE INDEX ix_info_id ON public.info USING btree (id);


--
-- Name: ix_info_key; Type: INDEX; Schema: public; Owner: cloud_man
--

CREATE INDEX ix_info_key ON public.info USING btree (key);


--
-- PostgreSQL database dump complete
--

