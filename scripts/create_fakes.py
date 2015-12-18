# -*- coding: utf-8 -*-
"""Fake data generator.

To use:

1. Install fake-factory.

    pip install fake-factory

2. Create your OSF user account

3. Run the script, passing in your username (email).
::

    python -m scripts.create_fakes --user fred@cos.io

This will create 3 fake public projects, each with 3 fake contributors (with
    you as the creator).
"""
from __future__ import print_function, absolute_import
import sys
import argparse
import logging
from modularodm.query.querydialect import DefaultQueryDialect as Q
from faker import Factory

from framework.auth import Auth
from website.app import init_app
from website import models, security
from framework.auth import utils
from tests.factories import UserFactory, ProjectFactory, NodeFactory, RegistrationFactory
from faker.providers import BaseProvider


class Sciencer(BaseProvider):
    # Science term Faker Provider created by @csheldonhess
    # https://github.com/csheldonhess/FakeConsumer/blob/master/faker/providers/science.py
    word_list = ('abiosis', 'abrade', 'absorption', 'acceleration', 'accumulation',
                 'acid', 'acidic', 'activist', 'adaptation', 'agonistic', 'agrarian', 'airborne',
                 'alchemist', 'alignment', 'allele', 'alluvial', 'alveoli', 'ambiparous',
                 'amphibian', 'amplitude', 'analysis', 'ancestor', 'anodize', 'anomaly',
                 'anther', 'antigen', 'apiary', 'apparatus', 'application', 'approximation',
                 'aquatic', 'aquifer', 'arboreal', 'archaeology', 'artery', 'assessment',
                 'asteroid', 'atmosphere', 'atomic', 'atrophy', 'attenuate', 'aven', 'aviary',
                 'axis', 'bacteria', 'balance', 'bases', 'biome', 'biosphere', 'black hole',
                 'blight', 'buoyancy', 'calcium', 'canopy', 'capacity', 'capillary', 'carapace',
                 'carcinogen', 'catalyst', 'cauldron', 'celestial', 'cells', 'centigrade',
                 'centimeter', 'centrifugal', 'chemical reaction', 'chemicals', 'chemistry',
                 'chlorophyll', 'choked', 'chromosome', 'chronic', 'churn', 'classification',
                 'climate', 'cloud', 'comet', 'composition', 'compound', 'compression',
                 'condensation', 'conditions', 'conduction', 'conductivity', 'conservation',
                 'constant', 'constellation', 'continental', 'convection', 'convention', 'cool',
                 'core', 'cosmic', 'crater', 'creature', 'crepuscular', 'crystals', 'cycle', 'cytoplasm',
                 'dampness', 'data', 'decay', 'decibel', 'deciduous', 'defoliate', 'density',
                 'denude', 'dependency', 'deposits', 'depth', 'desiccant', 'detritus',
                 'development', 'digestible', 'diluted', 'direction', 'disappearance', 'discovery',
                 'dislodge', 'displace', 'dissection', 'dissolution', 'dissolve', 'distance',
                 'diurnal', 'diverse', 'doldrums', 'dynamics', 'earthquake', 'eclipse', 'ecology',
                 'ecosystem', 'electricity', 'elements', 'elevation', 'embryo', 'endangered',
                 'endocrine', 'energy', 'entropy', 'environment', 'enzyme', 'epidermis', 'epoch',
                 'equilibrium', 'equine', 'erosion', 'essential', 'estuary', 'ethical', 'evaporation',
                 'event', 'evidence', 'evolution', 'examination', 'existence', 'expansion',
                 'experiment', 'exploration ', 'extinction', 'extreme', 'facet', 'fault', 'fauna',
                 'feldspar', 'fermenting', 'fission', 'fissure', 'flora', 'flourish', 'flowstone',
                 'foliage', 'food chain', 'forage', 'force', 'forecast', 'forensics', 'formations',
                 'fossil fuel', 'frequency', 'friction', 'fungi', 'fusion', 'galaxy', 'gastric',
                 'geo-science', 'geothermal', 'germination', 'gestation', 'global', 'gravitation',
                 'green', 'greenhouse effect', 'grotto', 'groundwater', 'habitat', 'heat', 'heavens',
                 'hemisphere', 'hemoglobin', 'herpetologist', 'hormones', 'host', 'humidity', 'hyaline',
                 'hydrogen', 'hydrology', 'hypothesis', 'ichthyology', 'illumination', 'imagination',
                 'impact of', 'impulse', 'incandescent', 'indigenous', 'inertia', 'inevitable', 'inherit',
                 'inquiry', 'insoluble', 'instinct', 'instruments', 'integrity', 'intelligence',
                 'interacts with', 'interdependence', 'interplanetary', 'invertebrate', 'investigation',
                 'invisible', 'ions', 'irradiate', 'isobar', 'isotope', 'joule', 'jungle', 'jurassic',
                 'jutting', 'kilometer', 'kinetics', 'kingdom', 'knot', 'laser', 'latitude', 'lava',
                 'lethal', 'life', 'lift', 'light', 'limestone', 'lipid', 'lithosphere', 'load',
                 'lodestone', 'luminous', 'luster', 'magma', 'magnet', 'magnetism', 'mangrove', 'mantle',
                 'marine', 'marsh', 'mass', 'matter', 'measurements', 'mechanical', 'meiosis', 'meridian',
                 'metamorphosis', 'meteor', 'microbes', 'microcosm', 'migration', 'millennia', 'minerals',
                 'modulate', 'moisture', 'molecule', 'molten', 'monograph', 'monolith', 'motion',
                 'movement', 'mutant', 'mutation', 'mysterious', 'natural', 'navigable', 'navigation',
                 'negligence', 'nervous system', 'nesting', 'neutrons', 'niche', 'nocturnal',
                 'nuclear energy', 'numerous', 'nurture', 'obsidian', 'ocean', 'oceanography', 'omnivorous',
                 'oolites (cave pearls)', 'opaque', 'orbit', 'organ', 'organism', 'ornithology',
                 'osmosis', 'oxygen', 'paleontology', 'parallax', 'particle', 'penumbra',
                 'percolate', 'permafrost', 'permutation', 'petrify', 'petrograph', 'phenomena',
                 'physical property', 'planetary', 'plasma', 'polar', 'pole', 'pollination',
                 'polymer', 'population', 'precipitation', 'predator', 'prehensile', 'preservation',
                 'preserve', 'pressure', 'primate', 'pristine', 'probe', 'process', 'propagation',
                 'properties', 'protected', 'proton', 'pulley', 'qualitative data', 'quantum', 'quark',
                 'quarry', 'radiation', 'radioactivity', 'rain forest', 'ratio', 'reaction', 'reagent',
                 'realm', 'redwoods', 'reeds', 'reflection', 'refraction', 'relationships between', 'reptile',
                 'research', 'resistance', 'resonate', 'rookery', 'rubble', 'runoff', 'salinity', 'sandbar',
                 'satellite', 'saturation', 'scientific investigation', 'scientist\'s', 'sea floor', 'season',
                 'sedentary', 'sediment', 'sedimentary', 'seepage', 'seismic', 'sensors', 'shard',
                 'similarity', 'solar', 'soluble', 'solvent', 'sonic', 'sound', 'source', 'species',
                 'spectacular', 'spectrum', 'speed', 'sphere', 'spring', 'stage', 'stalactite',
                 'stalagmites', 'stimulus', 'substance', 'subterranean', 'sulfuric acid', 'surface',
                 'survival', 'swamp', 'sylvan', 'symbiosis', 'symbol', 'synergy', 'synthesis', 'taiga',
                 'taxidermy', 'technology', 'tectonics', 'temperate', 'temperature', 'terrestrial',
                 'thermals', 'thermometer', 'thrust', 'torque', 'toxin', 'trade winds', 'pterodactyl',
                 'transformation tremors', 'tropical', 'umbra', 'unbelievable', 'underwater', 'unearth',
                 'unique', 'unite', 'unity', 'universal', 'unpredictable', 'unusual', 'ursine', 'vacuole',
                 'valuable', 'vapor', 'variable', 'variety', 'vast', 'velocity', 'ventifact', 'verdant',
                 'vespiary', 'viable', 'vibration', 'virus', 'viscosity', 'visible', 'vista', 'vital',
                 'vitreous', 'volt', 'volume', 'vulpine', 'wave', 'wax', 'weather', 'westerlies', 'wetlands',
                 'whitewater', 'xeriscape', 'xylem', 'yield', 'zero-impact', 'zone', 'zygote', 'achieving',
                 'acquisition of', 'an alternative', 'analysis of', 'approach toward', 'area', 'aspects of',
                 'assessment of', 'assuming', 'authority', 'available', 'benefit of', 'circumstantial',
                 'commentary', 'components', 'concept of', 'consistent', 'corresponding', 'criteria',
                 'data', 'deduction', 'demonstrating', 'derived', 'distribution', 'dominant', 'elements',
                 'equation', 'estimate', 'evaluation', 'factors', 'features', 'final', 'function',
                 'initial', 'instance ', 'interpretation of', 'maintaining ', 'method', 'perceived',
                 'percent', 'period', 'positive', 'potential', 'previous', 'primary', 'principle',
                 'procedure', 'process', 'range', 'region', 'relevant', 'required', 'research',
                 'resources', 'response', 'role', 'section', 'select', 'significant ', 'similar',
                 'source', 'specific', 'strategies', 'structure', 'theory', 'transfer', 'variables',
                 'corvidae', 'passerine', 'Pica pica', 'Chinchilla lanigera', 'Nymphicus hollandicus',
                 'Melopsittacus undulatus', )

    def science_word(cls):
        """
        :example 'Lorem'
        """
        return cls.random_element(cls.word_list)

    def science_words(cls, nb=3):
        """
        Generate an array of random words
        :example array('Lorem', 'ipsum', 'dolor')
        :param nb how many words to return
        """
        return [cls.science_word() for _ in range(0, nb)]

    def science_sentence(cls, nb_words=6, variable_nb_words=True):
        """
        Generate a random sentence
        :example 'Lorem ipsum dolor sit amet.'
        :param nb_words around how many words the sentence should contain
        :param variable_nb_words set to false if you want exactly $nbWords returned,
            otherwise $nbWords may vary by +/-40% with a minimum of 1
        """
        if nb_words <= 0:
            return ''

        if variable_nb_words:
            nb_words = cls.randomize_nb_elements(nb_words)

        words = cls.science_words(nb_words)
        words[0] = words[0].title()

        return " ".join(words) + '.'

    def science_sentences(cls, nb=3):
        """
        Generate an array of sentences
        :example array('Lorem ipsum dolor sit amet.', 'Consectetur adipisicing eli.')
        :param nb how many sentences to return
        :return list
        """
        return [cls.science_sentence() for _ in range(0, nb)]

    def science_paragraph(cls, nb_sentences=3, variable_nb_sentences=True):
        """
        Generate a single paragraph
        :example 'Sapiente sunt omnis. Ut pariatur ad autem ducimus et. Voluptas rem voluptas sint modi dolorem amet.'
        :param nb_sentences around how many sentences the paragraph should contain
        :param variable_nb_sentences set to false if you want exactly $nbSentences returned,
            otherwise $nbSentences may vary by +/-40% with a minimum of 1
        :return string
        """
        if nb_sentences <= 0:
            return ''

        if variable_nb_sentences:
            nb_sentences = cls.randomize_nb_elements(nb_sentences)

        return " ".join(cls.science_sentences(nb_sentences))

    def science_paragraphs(cls, nb=3):
        """
        Generate an array of paragraphs
        :example array($paragraph1, $paragraph2, $paragraph3)
        :param nb how many paragraphs to return
        :return array
        """
        return [cls.science_paragraph() for _ in range(0, nb)]

    def science_text(cls, max_nb_chars=200):
        """
        Generate a text string.
        Depending on the $maxNbChars, returns a string made of words, sentences, or paragraphs.
        :example 'Sapiente sunt omnis. Ut pariatur ad autem ducimus et. Voluptas rem voluptas sint modi dolorem amet.'
        :param max_nb_chars Maximum number of characters the text should contain (minimum 5)
        :return string
        """
        text = []
        if max_nb_chars < 5:
            raise ValueError('text() can only generate text of at least 5 characters')

        if max_nb_chars < 25:
            # join words
            while not text:
                size = 0
                # determine how many words are needed to reach the $max_nb_chars once;
                while size < max_nb_chars:
                    word = (' ' if size else '') + cls.science_word()
                    text.append(word)
                    size += len(word)
                text.pop()
            text[0] = text[0][0].upper() + text[0][1:]
            last_index = len(text) - 1
            text[last_index] += '.'
        elif max_nb_chars < 100:
            # join sentences
            while not text:
                size = 0
                # determine how many sentences are needed to reach the $max_nb_chars once
                while size < max_nb_chars:
                    sentence = (' ' if size else '') + cls.science_sentence()
                    text.append(sentence)
                    size += len(sentence)
                text.pop()
        else:
            # join paragraphs
            while not text:
                size = 0
                # determine how many paragraphs are needed to reach the $max_nb_chars once
                while size < max_nb_chars:
                    paragraph = ('\n' if size else '') + cls.science_paragraph()
                    text.append(paragraph)
                    size += len(paragraph)
                text.pop()

        return "".join(text)


logger = logging.getLogger('create_fakes')
logging.basicConfig(level=logging.ERROR)
fake = Factory.create()
fake.add_provider(Sciencer)


def create_fake_user():
    email = fake.email()
    name = fake.name()
    parsed = utils.impute_names(name)
    user = UserFactory(username=email, fullname=name,
                       is_registered=True, is_claimed=True,
                       verification_key=security.random_string(15),
                       date_registered=fake.date_time(),
                       emails=[email],
                       **parsed
                   )
    user.set_password('faker123')
    user.save()
    logger.info('Created user: {0} <{1}>'.format(user.fullname, user.username))
    return user


def parse_args():
    parser = argparse.ArgumentParser(description='Create fake data.')
    parser.add_argument('-u', '--user', dest='user', required=True)
    parser.add_argument('--nusers', dest='n_users', type=int, default=3)
    parser.add_argument('--nprojects', dest='n_projects', type=int, default=3)
    parser.add_argument('--ncomponents', dest='n_components', type=int, default=0)
    parser.add_argument('-p', '--privacy', dest="privacy", type=str, default='private', choices=['public', 'private'])
    parser.add_argument('-n', '--name', dest='name', type=str, default=None)
    parser.add_argument('-t', '--tags', dest='n_tags', type=int, default=5)
    parser.add_argument('--presentation', dest='presentation_name', type=str, default=None)
    parser.add_argument('-r', '--registration', dest='is_registration', type=bool, default=False)
    return parser.parse_args()


def create_fake_project(creator, n_users, privacy, n_components, name, n_tags, presentation_name, is_registration):
    auth = Auth(user=creator)
    project_title = name if name else fake.science_sentence()
    if not is_registration:
        project = ProjectFactory(title=project_title, description=fake.science_paragraph(), creator=creator)
    else:
        project = RegistrationFactory(title=project_title, description=fake.science_paragraph(), creator=creator)
    project.set_privacy(privacy)
    for _ in range(n_users):
        contrib = create_fake_user()
        project.add_contributor(contrib, auth=auth)
    for _ in range(n_components):
        NodeFactory(project=project, title=fake.science_sentence(), description=fake.science_paragraph(),
                    creator=creator)
    for _ in range(n_tags):
        project.add_tag(fake.science_word(), auth=auth)
    if presentation_name is not None:
        project.add_tag(presentation_name, auth=auth)
        project.add_tag('poster', auth=auth)

    project.save()
    logger.info('Created project: {0}'.format(project.title))
    return project


def main():
    args = parse_args()
    creator = models.User.find(Q('username', 'eq', args.user))[0]
    for i in range(args.n_projects):
        name = args.name + str(i) if args.name else ''
        create_fake_project(creator, args.n_users, args.privacy, args.n_components, name, args.n_tags,
                            args.presentation_name, args.is_registration)
    print('Created {n} fake projects.'.format(n=args.n_projects))
    sys.exit(0)


if __name__ == '__main__':
    init_app(set_backends=True, routes=False)
    main()
