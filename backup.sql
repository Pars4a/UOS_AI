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
\.


--
-- Name: info_id_seq; Type: SEQUENCE SET; Schema: public; Owner: cloud_man
--

SELECT pg_catalog.setval('public.info_id_seq', 9, true);


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

